from aiogram.fsm.state import State, StatesGroup

class PresentationForm(StatesGroup):
    template_selection = State()
    custom_design_prompt = State()
    ocr_photo_upload = State()
    subject = State()
    topic = State()
    slide_count = State()
    author_name = State()
    institution = State()
    level = State()
    course = State()
    teacher_name = State()
    logo_upload = State()
    date = State()
    language = State()
    notes_choice = State()
    additional_notes = State()
    confirmation = State()
    outline_review = State()
    outline_edit = State()
    outline_wait = State()   # AI is writing the plan (buttons pressed twice are ignored)
    generating = State()     # slides are being written and rendered

class PaymentForm(StatesGroup):
    waiting_for_payment = State()

class AdminForm(StatesGroup):
    set_price_per_slide = State()
    set_min_slides = State()
