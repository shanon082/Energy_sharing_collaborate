import logging
import re
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import timedelta
from typing import Tuple, Union
from django.conf import settings
from django.utils import timezone
from psycopg2 import Binary
from six import text_type
from accounts.models import (
    User,
    Wallet,
    Profile,
    generate_random_string
)
from utils.general import bytes2str


logger = logging.getLogger(__name__)
ENCODED_HASH_PATTERN = r"(?:[\w\d+/]{4})*(?:[\w\d+/]{2}==|[\w\d+/]{3}=)?"
HASH_PATTERN = "user:[0-9]*"


def b64encode_user(user_id):
    """
    returns urlsafe b64 encoded pattern given user id

    :param user_id: id of accounts.User
    :type user_id: int

    :returns: str used as user_hash
    """
    encoded = bytes2str(urlsafe_b64encode, "user:{}".format(user_id))
    return encoded


def b64decode_hash(
    hash_str: str,
) -> Union[Tuple[None, None], Tuple[str, str]]:
    """
    Given a hash that matches , decodes hash and returns
    tuple of the Model and Model.id

    :param hash_str: b64encoded string matching HASH_PATTERN
    :type org_hash: str

    :returns: tuple ('user', object_id)
    """
    if not re.match(ENCODED_HASH_PATTERN, hash_str):
        return None, None

    decoded_bytes = urlsafe_b64decode(text_type(hash_str))
    try:
        decoded_param = decoded_bytes.decode("utf8")
    except UnicodeDecodeError:
        return None, None
    if not re.match(HASH_PATTERN, decoded_param):
        return None, None

    model, model_id = decoded_param.split(":")
    return model, model_id


def get_diff_repr(diff_date):
    """
    Takes date difference and returns a string representation

    :param diff_date: datetime.timedelta(seconds=7656, microseconds=929673)

    :returns: "01 mins, 23 secs"
    """
    diff_seconds = diff_date.total_seconds()
    s = diff_seconds
    m = s // 60
    diff_repr = "%02d mins, %02d secs" % (m % 60, s % 60)
    return diff_repr


def get_should_resend(message):
    """
    Determines whether we should resend a code using the message provider

    :param message: accounts.PhoneVerificationMessage

    :returns: (bool, message)
    """
    BACK_OFF = int(settings.PHONE_VERIFICATION_BACK_OFF_MINUTES)
    now = timezone.now()

    if message.create_date < (now - timedelta(minutes=BACK_OFF)):
        return (True, "")

    diff = message.create_date + timedelta(minutes=BACK_OFF) - now
    diff_repr = get_diff_repr(diff)
    return (False, f"Please try again in {diff_repr}")


def validate_user_hash(user_hash):
    try:
        _, user_id = b64decode_hash(user_hash)
        user = User.objects.get(pk=user_id)
        return user
    except User.DoesNotExist:
        return None
    except Exception as e:
        logger.exception(
            f"[RESET PASSWORD] Error while decoding uid.\n"
            f"Error: {text_type(e)}"
        )
        return None


def handle_post_email_verification(user):
    # activate account

    logger.info(f"[ACCOUNT_ACTIVATION] Activated user account {user.id}")

    # create wallet
    currency = getattr(settings, 'DEFAULT_CURRENCY', 'USD')

    wallet, created = Wallet.objects.get_or_create(
        user=user, currency=currency
    )
    if created:
        logger.info(f"[ACCOUNT_ACTIVATION] Created wallet {wallet.id}")


def create_admin_provisioned_user(*, owner_name, email, phone_number):
    """
    Create a client account from the admin meter registration flow.
    The owner sets a password through the existing email reset flow.
    """
    email = (email or "").strip().lower()
    phone_number = (phone_number or "").strip()
    owner_name = (owner_name or "").strip()

    if not owner_name or not email or not phone_number:
        raise ValueError("owner_name, owner_email, and owner_phone are required")

    if User.objects.filter(email=email).exists():
        raise ValueError("A user with this email already exists")

    if User.objects.filter(phone_number=phone_number).exists():
        raise ValueError("A user with this phone number already exists")

    parts = owner_name.split(None, 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else first_name

    user = User(
        email=email,
        first_name=first_name,
        last_name=last_name,
        phone_number=phone_number,
        user_role=User.CLIENT,
        account_is_active=True,
        must_change_password=True,
    )
    user.set_unusable_password()
    user.save()

    Profile.objects.filter(user=user).update(email_verified=True)
    handle_post_email_verification(user)

    logger.info(f"[ADMIN] Provisioned client user {user.id} ({email}) with meter onboarding")
    return user


def check_if_in_team(upline, origin):
    if not upline:
        return False
    if upline.id < origin.id:
        return False
    elif upline.id == origin.id:
        return True
    else:
        print(f"[SKIPPING] {upline.user_id.email}")
        upline_binary = Binary.objects.filter(user_id=upline.upline_id).first()
        return check_if_in_team(upline_binary, origin)


def activate_admin(admin_id):
    admin_user = User.objects.filter(id=admin_id, email=settings.ADMIN_EMAIL).first()
    if not admin_user:
        raise Exception("Invalid admin user")

    
    admin_user.referral_code = generate_random_string(10)
    admin_user.save()
    return True


def calculate_credit_score(responses):
    """
    Calculate credit score based on questionnaire responses
    """
    scoring_rules = {
        'Q1': {  # Monthly Expenditure
            '>100,000 UGX': 100,
            '50,000–100,000 UGX': 75,
            '20,000–49,999 UGX': 50,
            '<20,000 UGX': 25
        },
        'Q2': {  # Purchase Frequency
            'Weekly': 100,
            'Biweekly': 75,
            'Monthly': 50,
            'Rarely': 25
        },
        'Q3': {  # Payment Consistency
            'Always on time': 100,
            'Often on time': 75,
            'Sometimes late': 50,
            'Mostly late': 25
        },
        'Q4': {  # Disconnection History
            'No disconnections': 100,
            '1–2 disconnections': 70,
            '3–4 disconnections': 40,
            '>4 disconnections': 10
        },
        'Q5': {  # Meter Sharing
            'No sharing': 100,
            'Shared': 50
        },
        'Q6': {  # Monthly Income
            '>1,000,000 UGX': 100,
            '500,000–999,999 UGX': 75,
            '200,000–499,999 UGX': 50,
            '<200,000 UGX': 25
        },
        'Q7': {  # Income Stability
            'Fixed and stable': 100,
            'Irregular but frequent': 75,
            'Seasonal income': 50,
            'Unstable income': 25
        },
        'Q8': {  # Consumption Level
            'High (>200 kWh)': 100,
            'Medium (100–200 kWh)': 75,
            'Low (50–99 kWh)': 50,
            'Very low (<50 kWh)': 25
        }
    }
    
    weights = {
        'Q1': 0.15, 'Q2': 0.10, 'Q3': 0.30, 'Q4': 0.20,
        'Q5': 0.03, 'Q6': 0.07, 'Q7': 0.05, 'Q8': 0.10
    }
    
    total_score = 0
    for question, response in responses.items():
        if question in scoring_rules and response in scoring_rules[question]:
            question_score = scoring_rules[question][response]
            total_score += question_score * weights[question]
    
    return round(total_score)

def determine_loan_tier(credit_score):
    """Determine loan tier based on credit score"""
    if credit_score < 60:
        return None  # Not eligible
    elif 60 <= credit_score < 70:
        return 1
    elif 70 <= credit_score < 80:
        return 2
    elif 80 <= credit_score < 90:
        return 3
    else:
        return 4

def calculate_loan_amount(tier, max_loan=200000):
    """Calculate loan amount based on tier"""
    tier_amounts = {
        1: max_loan * 0.25,  # 50,000
        2: max_loan * 0.50,  # 100,000
        3: max_loan * 0.75,  # 150,000
        4: max_loan * 1.00   # 200,000
    }
    return tier_amounts.get(tier, 0)
