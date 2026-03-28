from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class AmbulanceTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = getattr(user, "role", "")
        token["username"] = user.username
        return token
