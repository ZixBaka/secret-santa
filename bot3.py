import asyncio
import random
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Replace with your bot token
BOT_TOKEN = "8243389992:AAExt0gfcCYGpdau-feKhPYeTdhQIqBp8Ko"

# Storage for events and user profiles
events = {}
user_profiles = {}  # {user_id: {"full_name": "Name", "registered": True}}

class EventStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_user_fullname = State()
    selecting_preassignment = State()

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

def get_user_event(user_id):
    """Find the event a user is part of"""
    for event_name, data in events.items():
        if user_id in data["participants"] or user_id == data["organizer"]:
            return event_name, data
    return None, None

def get_user_name(user_id):
    """Get user's registered full name"""
    if user_id in user_profiles:
        return user_profiles[user_id]["full_name"]
    return "Unknown User"

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id

    # Check if user is already registered
    if user_id not in user_profiles:
        await state.set_state(EventStates.waiting_for_user_fullname)
        await message.answer(
            "👋 Welcome to Secret Santa Bot! 🎄\n\n"
            "Before you start, please enter your full name (this will be shown to other participants):"
        )
        return

    await message.answer(
        f"🎅 Welcome back, {user_profiles[user_id]['full_name']}! 🎄\n\n"
        "Commands:\n"
        "/create - Create a new Secret Santa event\n"
        "/join - Join an existing event\n"
        "/list - List all active events\n"
        "/participants - See who joined your event\n"
        "/preselect - Choose who you want to give to (if allowed)\n"
        "/allow_preselect - Toggle pre-selection (organizer only)\n"
        "/draw - Start the draw (organizer only)\n"
        "/myevent - See your current event\n"
        "/myname - Change your registered name\n"
        "/leave - Leave current event"
    )

@dp.message(EventStates.waiting_for_user_fullname)
async def process_user_fullname(message: Message, state: FSMContext):
    full_name = message.text.strip()
    user_id = message.from_user.id

    if len(full_name) < 2:
        await message.answer("❌ Please enter a valid name (at least 2 characters).")
        return

    user_profiles[user_id] = {
        "full_name": full_name,
        "registered": True
    }

    await state.clear()
    await message.answer(
        f"✅ Welcome, {full_name}! 🎄\n\n"
        "You're all set! Here are the commands:\n\n"
        "/create - Create a new Secret Santa event\n"
        "/join - Join an existing event\n"
        "/list - List all active events\n"
        "/participants - See who joined your event\n"
        "/preselect - Choose who you want to give to (if allowed)\n"
        "/allow_preselect - Toggle pre-selection (organizer only)\n"
        "/draw - Start the draw (organizer only)\n"
        "/myevent - See your current event\n"
        "/myname - Change your registered name\n"
        "/leave - Leave current event"
    )

@dp.message(Command("myname"))
async def cmd_myname(message: Message, state: FSMContext):
    user_id = message.from_user.id

    if user_id in user_profiles:
        current_name = user_profiles[user_id]["full_name"]
        await message.answer(f"Your current name: {current_name}\n\nEnter a new name to change it:")
    else:
        await message.answer("Please enter your full name:")

    await state.set_state(EventStates.waiting_for_user_fullname)

@dp.message(Command("create"))
async def cmd_create(message: Message, state: FSMContext):
    user_id = message.from_user.id

    if user_id not in user_profiles:
        await message.answer("❌ Please use /start first to register your name.")
        return

    await state.set_state(EventStates.waiting_for_name)
    await message.answer("Please enter a name for your Secret Santa event:")

@dp.message(EventStates.waiting_for_name)
async def process_event_name(message: Message, state: FSMContext):
    event_name = message.text.strip()
    user_id = message.from_user.id

    if event_name in events:
        await message.answer("❌ Event with this name already exists. Please choose another name.")
        return

    events[event_name] = {
        "organizer": user_id,
        "organizer_name": get_user_name(user_id),
        "participants": {},
        "drawn": False,
        "allow_preselect": False,
        "preassignments": {}  # {giver_id: receiver_id}
    }

    await state.clear()
    await message.answer(
        f"✅ Event '{event_name}' created!\n\n"
        f"Share this name with others so they can join using /join\n\n"
        f"⚙️ Use /allow_preselect to let participants choose their gift recipients\n"
        f"🎁 When ready, use /draw to assign Secret Santas!"
    )

@dp.message(Command("allow_preselect"))
async def cmd_allow_preselect(message: Message):
    user_id = message.from_user.id
    event_name, data = get_user_event(user_id)

    if not event_name:
        await message.answer("❌ You're not part of any event.")
        return

    if user_id != data["organizer"]:
        await message.answer("❌ Only the organizer can change this setting.")
        return

    if data["drawn"]:
        await message.answer("❌ Cannot change settings after draw!")
        return

    data["allow_preselect"] = not data["allow_preselect"]
    status = "ENABLED ✅" if data["allow_preselect"] else "DISABLED ❌"

    await message.answer(
        f"Pre-selection is now {status}\n\n"
        f"{'Participants can now use /preselect to choose who they give to!' if data['allow_preselect'] else 'Participants cannot pre-select recipients.'}"
    )

@dp.message(Command("preselect"))
async def cmd_preselect(message: Message):
    user_id = message.from_user.id

    if user_id not in user_profiles:
        await message.answer("❌ Please use /start first to register your name.")
        return

    event_name, data = get_user_event(user_id)

    if not event_name:
        await message.answer("❌ You're not part of any event. Use /join to join one.")
        return

    if not data["allow_preselect"]:
        await message.answer("❌ Pre-selection is not enabled for this event. Ask the organizer to enable it with /allow_preselect")
        return

    if data["drawn"]:
        await message.answer("❌ Secret Santas have already been drawn!")
        return

    if user_id not in data["participants"]:
        await message.answer("❌ You must be a participant to pre-select.")
        return

    # Create inline keyboard with ALL other participants
    keyboard = []
    for participant_id, participant_name in data["participants"].items():
        if participant_id != user_id:  # Can't select yourself
            keyboard.append([InlineKeyboardButton(
                text=f"{'✅ ' if data['preassignments'].get(user_id) == participant_id else ''}{participant_name}",
                callback_data=f"preselect:{event_name}:{participant_id}"
            )])

    # Add "Clear Selection" button if user has made a selection
    if user_id in data["preassignments"]:
        keyboard.append([InlineKeyboardButton(text="🗑 Clear My Selection", callback_data="preselect:clear")])

    keyboard.append([InlineKeyboardButton(text="❌ Cancel", callback_data="preselect:cancel")])

    current = data["preassignments"].get(user_id)
    current_text = f"\n\n🎁 Currently selected: {data['participants'][current]}" if current else ""

    await message.answer(
        f"🎅 Choose who you want to give a gift to:{current_text}\n\n"
        f"Note: Multiple people can select the same person. Conflicts will be shown to the organizer during draw.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@dp.callback_query(F.data.startswith("preselect:"))
async def process_preselect(callback: CallbackQuery):
    data_parts = callback.data.split(":")

    if data_parts[1] == "cancel":
        await callback.message.delete()
        await callback.answer("Cancelled")
        return

    if data_parts[1] == "clear":
        giver_id = callback.from_user.id
        event_name, data = get_user_event(giver_id)

        if event_name and giver_id in data["preassignments"]:
            del data["preassignments"][giver_id]
            await callback.message.delete()
            await callback.message.answer("✅ Your pre-selection has been cleared.")
            await callback.answer()
        else:
            await callback.answer("No selection to clear!", show_alert=True)
        return

    event_name = data_parts[1]
    receiver_id = int(data_parts[2])
    giver_id = callback.from_user.id

    if event_name not in events:
        await callback.answer("Event no longer exists!", show_alert=True)
        return

    data = events[event_name]

    # Allow selection even if someone else selected the same person
    data["preassignments"][giver_id] = receiver_id
    receiver_name = data["participants"][receiver_id]

    await callback.message.delete()
    await callback.message.answer(
        f"✅ You've pre-selected: {receiver_name}\n\n"
        f"You can change or clear this anytime with /preselect before the draw.\n\n"
        f"⚠️ Note: If multiple people select the same person, the organizer will see a conflict warning during draw."
    )
    await callback.answer()

@dp.message(Command("join"))
async def cmd_join(message: Message):
    user_id = message.from_user.id

    if user_id not in user_profiles:
        await message.answer("❌ Please use /start first to register your name.")
        return

    if not events:
        await message.answer("❌ No events available. Create one with /create")
        return

    event_list = "\n".join([f"• {name}" for name in events.keys()])
    await message.answer(
        f"Available events:\n{event_list}\n\n"
        f"Reply with the event name you want to join:"
    )

@dp.message(Command("list"))
async def cmd_list(message: Message):
    if not events:
        await message.answer("No active events.")
        return

    event_info = []
    for name, data in events.items():
        status = "✅ Drawn" if data["drawn"] else "⏳ Waiting"
        preselect = "✅" if data["allow_preselect"] else "❌"
        precount = len(data["preassignments"])
        event_info.append(
            f"🎄 {name}\n"
            f"   Organizer: {data['organizer_name']}\n"
            f"   Participants: {len(data['participants'])}\n"
            f"   Pre-selection: {preselect} ({precount} set)\n"
            f"   Status: {status}"
        )

    await message.answer("Active Events:\n\n" + "\n\n".join(event_info))

@dp.message(Command("participants"))
async def cmd_participants(message: Message):
    user_id = message.from_user.id
    event_name, data = get_user_event(user_id)

    if not event_name:
        await message.answer("❌ You're not part of any event. Use /join to join one.")
        return

    participants_list = []
    for pid, pname in data["participants"].items():
        # Only show marker for own pre-selection if you're that person
        marker = ""
        if user_id == data["organizer"]:
            # Organizer sees who has pre-selected (but not who they selected)
            if pid in data["preassignments"]:
                marker = " 🎁"
        elif pid == user_id and user_id in data["preassignments"]:
            # You only see your own pre-selection marker
            marker = " 🎁"

        participants_list.append(f"• {pname}{marker}")

    preselect_status = "Enabled ✅" if data["allow_preselect"] else "Disabled ❌"

    marker_explanation = ""
    if user_id == data["organizer"]:
        marker_explanation = "\n🎁 = Has pre-selected someone"
    elif user_id in data["preassignments"]:
        marker_explanation = "\n🎁 = You have pre-selected someone"

    await message.answer(
        f"🎄 Event: {event_name}\n"
        f"Pre-selection: {preselect_status}\n"
        f"👥 Participants ({len(data['participants'])}):\n" + "\n".join(participants_list) + marker_explanation
    )

@dp.message(Command("draw"))
async def cmd_draw(message: Message):
    user_id = message.from_user.id
    event_name, data = get_user_event(user_id)

    if not event_name or user_id != data["organizer"]:
        await message.answer("❌ You must be the organizer to start the draw.")
        return

    if len(data["participants"]) < 2:
        await message.answer("❌ Need at least 2 participants to draw!")
        return

    if data["drawn"]:
        await message.answer("❌ Secret Santas have already been drawn for this event!")
        return

    # Check for conflicts (multiple people selecting the same person)
    conflicts = {}
    for giver, receiver in data["preassignments"].items():
        if receiver not in conflicts:
            conflicts[receiver] = []
        conflicts[receiver].append(giver)

    conflict_list = [(receiver, givers) for receiver, givers in conflicts.items() if len(givers) > 1]

    if conflict_list:
        conflict_msg = "⚠️ PRE-SELECTION CONFLICTS DETECTED:\n\n"
        for receiver_id, giver_ids in conflict_list:
            receiver_name = data["participants"][receiver_id]
            giver_names = [data["participants"][gid] for gid in giver_ids]
            conflict_msg += f"🎁 {receiver_name} is pre-selected by:\n"
            for gname in giver_names:
                conflict_msg += f"   • {gname}\n"
            conflict_msg += "\n"

        conflict_msg += "Please resolve conflicts before drawing. Ask participants to change their selections using /preselect"
        await message.answer(conflict_msg)
        return

    # Perform the draw with pre-assignments
    participants = list(data["participants"].keys())
    assignments = {}

    # Start with pre-assignments
    for giver, receiver in data["preassignments"].items():
        if giver in participants and receiver in participants:
            assignments[giver] = receiver

    # Get remaining givers and receivers
    remaining_givers = [p for p in participants if p not in assignments]
    remaining_receivers = [p for p in participants if p not in assignments.values()]

    # Try to assign the rest
    valid = False
    attempts = 0
    while not valid and attempts < 1000:
        temp_assignments = assignments.copy()
        temp_receivers = remaining_receivers.copy()
        random.shuffle(temp_receivers)

        valid_attempt = True
        for giver in remaining_givers:
            # Find a receiver that isn't the giver
            assigned = False
            for i, receiver in enumerate(temp_receivers):
                if giver != receiver:
                    temp_assignments[giver] = receiver
                    temp_receivers.pop(i)
                    assigned = True
                    break

            if not assigned:
                valid_attempt = False
                break

        if valid_attempt and len(temp_assignments) == len(participants):
            assignments = temp_assignments
            valid = True

        attempts += 1

    if not valid:
        await message.answer("❌ Could not create valid assignments with current pre-selections. Try removing some pre-selections.")
        return

    # Send private messages to each participant
    data["drawn"] = True
    success_count = 0
    preassigned_count = sum(1 for giver in assignments if giver in data["preassignments"])

    for giver_id, receiver_id in assignments.items():
        receiver_name = data["participants"][receiver_id]
        was_preselected = giver_id in data["preassignments"] and data["preassignments"][giver_id] == receiver_id

        try:
            msg = (
                f"🎅 Your Secret Santa assignment for '{event_name}':\n\n"
                f"🎁 You are giving a gift to: {receiver_name}\n"
            )
            if was_preselected:
                msg += "\n✅ This was your pre-selected choice!\n"
            msg += "\nKeep it secret! 🤫"

            await bot.send_message(giver_id, msg)
            success_count += 1
        except Exception as e:
            print(f"Failed to send message to {giver_id}: {e}")

    await message.answer(
        f"✅ Secret Santa draw complete!\n"
        f"📬 Sent {success_count}/{len(participants)} assignments via DM.\n"
        f"🎁 {preassigned_count} pre-selected assignments honored.\n\n"
        f"⚠️ If someone didn't receive their assignment, they need to start a chat with the bot first!"
    )

@dp.message(Command("myevent"))
async def cmd_myevent(message: Message):
    user_id = message.from_user.id
    event_name, data = get_user_event(user_id)

    if not event_name:
        await message.answer("❌ You're not part of any event.")
        return

    status = "✅ Drawn" if data["drawn"] else "⏳ Waiting for draw"
    role = "Organizer" if user_id == data["organizer"] else "Participant"
    preselect = "Yes" if data["allow_preselect"] else "No"

    msg = (
        f"🎄 Your Event: {event_name}\n"
        f"👤 Your Role: {role}\n"
        f"👥 Participants: {len(data['participants'])}\n"
        f"🎁 Pre-selection allowed: {preselect}\n"
        f"📊 Status: {status}"
    )

    if user_id in data["preassignments"] and not data["drawn"]:
        receiver_name = data["participants"][data["preassignments"][user_id]]
        msg += f"\n\n✅ You've pre-selected: {receiver_name}"

    await message.answer(msg)

@dp.message(Command("leave"))
async def cmd_leave(message: Message):
    user_id = message.from_user.id
    event_name, data = get_user_event(user_id)

    if not event_name:
        await message.answer("❌ You're not part of any event.")
        return

    if user_id not in data["participants"]:
        await message.answer("❌ You're not a participant in this event.")
        return

    if data["drawn"]:
        await message.answer("❌ Cannot leave after Secret Santas have been drawn!")
        return

    # Remove user and their pre-assignments
    del data["participants"][user_id]
    if user_id in data["preassignments"]:
        del data["preassignments"][user_id]

    # Remove any pre-assignments to this user
    data["preassignments"] = {k: v for k, v in data["preassignments"].items() if v != user_id}

    await message.answer(f"✅ You left the event '{event_name}'")

@dp.message(F.text)
async def handle_text(message: Message):
    user_id = message.from_user.id

    if user_id not in user_profiles:
        await message.answer("❌ Please use /start first to register your name.")
        return

    # Check if user is trying to join an event
    event_name = message.text.strip()

    if event_name in events:
        user_name = get_user_name(user_id)

        # Check if already in another event
        for e_name, e_data in events.items():
            if user_id in e_data["participants"]:
                await message.answer(f"❌ You're already in event '{e_name}'. Use /leave first.")
                return

        if events[event_name]["drawn"]:
            await message.answer("❌ This event has already drawn Secret Santas!")
            return

        events[event_name]["participants"][user_id] = user_name

        preselect_msg = "\n🎁 Use /preselect to choose your gift recipient!" if events[event_name]["allow_preselect"] else ""

        await message.answer(
            f"✅ Successfully joined '{event_name}'!\n"
            f"👥 Total participants: {len(events[event_name]['participants'])}{preselect_msg}\n\n"
            f"Wait for the organizer to start the draw with /draw"
        )
    else:
        await message.answer("🤔 Not sure what you mean. Use /start to see available commands.")

async def main():
    print("Bot started...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
