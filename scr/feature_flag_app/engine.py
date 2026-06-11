import hashlib
from scr.feature_flag_app.models import FeatureFlag


def calculate_user_score(user_id: str, flag_name: str) -> int:
    """
    Deterministically hashes a user_id with a flag_name
    to return a consistent integer score between 0 and 99.
    """
    # Combining user_id and flag_name prevents the same users
    # from getting stuck in the "lucky 10%" tier across every single flag.
    salt_string = f"{user_id}:{flag_name}"

    # Generate an MD5 hex digest
    hash_object = hashlib.md5(salt_string.encode("utf-8"))
    hash_hex = hash_object.hexdigest()

    # Convert the first 8 characters of the hex string into an integer
    hash_int = int(hash_hex[:8], 16)

    # Modulo 100 gives us a consistent index range from 0 to 99
    return hash_int % 100


def evaluate_flag(user_id: str, flag: FeatureFlag, user_attributes: dict) -> bool:
    """
    Applies the cascading flag rules to decide if a feature is unlocked for a user.
    """
    # 1. Global Kill-Switch Check
    if not flag.is_enabled:
        return False

    # 2. Evaluate rules sequentially (Cascade Order)
    for rule in flag.rules:
        # Rule Type A: Whitelist check (Immediate Access override)
        if rule.rule_type == "user_whitelist":
            allowed_users = [u.strip() for u in rule.value.split(",")]
            if user_id in allowed_users:
                return True

        # Rule Type B: User Attribute Matching (e.g., tier == "premium")
        elif rule.rule_type == "attribute_match":
            # rule.value syntax example: "tier:premium"
            attr_key, attr_val = rule.value.split(":")
            if user_attributes.get(attr_key) == attr_val:
                return True

        # Rule Type C: Percentage Rollout
        elif rule.rule_type == "percentage":
            threshold = int(rule.value)  # e.g., "10"
            user_score = calculate_user_score(user_id, flag.name)

            # If the user's deterministic score falls within the threshold tier, unlock!
            if user_score < threshold:
                return True

    # Default fallback if no rules explicitly matched or unlocked the flag
    return False
