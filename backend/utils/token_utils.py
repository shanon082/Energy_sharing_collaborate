import jwt
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


def create_tokens_for_user(user):
    """
    Create JWT tokens for a user using HS256 algorithm
    """
    refresh = RefreshToken.for_user(user)
    
    # Add custom claims if needed
    refresh['email'] = user.email
    refresh['first_name'] = user.first_name
    refresh['last_name'] = user.last_name
    
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'user': {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone_number': str(user.phone_number),
        }
    }


def validate_token(token):
    """
    Validate a JWT token and return the payload
    """
    try:
        # Decode the token using HS256
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=['HS256'],
            options={'verify_exp': True}
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise InvalidToken('Token has expired')
    except jwt.InvalidTokenError as e:
        raise InvalidToken(f'Invalid token: {str(e)}')
    except Exception as e:
        logger.error(f"Token validation error: {str(e)}")
        raise InvalidToken('Token validation failed')


def get_user_from_token(token):
    """
    Extract user from JWT token
    """
    try:
        # For SimpleJWT tokens
        access_token = AccessToken(token)
        user_id = access_token['user_id']
        
        try:
            user = User.objects.get(id=user_id)
            return user
        except User.DoesNotExist:
            raise InvalidToken('User not found')
            
    except TokenError as e:
        raise InvalidToken(str(e))
    except Exception as e:
        logger.error(f"Error getting user from token: {str(e)}")
        raise InvalidToken('Failed to extract user from token')


def refresh_access_token(refresh_token):
    """
    Refresh an access token using a refresh token
    """
    try:
        refresh = RefreshToken(refresh_token)
        access_token = str(refresh.access_token)
        
        # Verify the refresh token is still valid
        refresh.verify()
        
        return {
            'access': access_token,
            'refresh': str(refresh)
        }
    except TokenError as e:
        raise InvalidToken(f'Invalid refresh token: {str(e)}')
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise InvalidToken('Failed to refresh token')