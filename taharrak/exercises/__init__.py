"""
Exercise registry for Taharrak.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  HOW TO ADD A NEW EXERCISE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. Create taharrak/exercises/my_exercise.py
     Define a single Exercise instance (see bicep_curl.py as a template).

  2. Import it below and add it to EXERCISES with a unique single-char key.

  That's it — nothing else in the codebase needs to change.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from .base             import Exercise, TechniqueProfile  # re-export for convenience
from .bicep_curl       import BICEP_CURL
from .shoulder_press   import SHOULDER_PRESS
from .lateral_raise    import LATERAL_RAISE
from .tricep_extension import TRICEP_EXTENSION
from .squat            import SQUAT

# Keys must be unique single characters that the user will press to select.
EXERCISES: dict[str, Exercise] = {
    "1": BICEP_CURL,
    "2": SHOULDER_PRESS,
    "3": LATERAL_RAISE,
    "4": TRICEP_EXTENSION,
    "5": SQUAT,
    # "6": MY_NEW_EXERCISE,   ← add here after creating its file
}

__all__ = ["Exercise", "TechniqueProfile", "EXERCISES"]
