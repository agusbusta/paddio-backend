from enum import Enum


class CategoryRestrictionType(str, Enum):
    NONE = "NONE"
    SAME_CATEGORY = "SAME_CATEGORY"
    NEARBY_CATEGORIES = "NEARBY_CATEGORIES"
