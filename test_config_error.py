"""Test config error handling."""

from pathlib import Path
from launchsampler.exceptions import ConfigFileInvalidError
from launchsampler.utils.error_handler import wrap_pydantic_error, format_error_for_display
from pydantic import ValidationError
from launchsampler.models import AppConfig

# Simulate the error from your log
error_msg = """1 validation error for AppConfig
  Invalid JSON: trailing comma at line 10 column 1 [type=json_invalid, input_value='{\n  "sets_dir": "C:\\...  "auto_save": true,\n}', input_type=str]"""

# Test our error conversion
try:
    # This would be the actual error
    class FakeValidationError(Exception):
        def __str__(self):
            return error_msg
    
    error = wrap_pydantic_error(FakeValidationError(), "C:\Users\afauc\.launchsampler\config.json")
    
    print("Exception Type:", type(error).__name__)
    print("\nUser Message:", error.user_message)
    print("\nTechnical Message:", error.technical_message)
    print("\nRecovery Hint:", error.recovery_hint)
    print("\n" + "="*70)
    print("WHAT USER WILL SEE:")
    print("="*70)
    
    user_msg, recovery = format_error_for_display(error)
    print(f"\nERROR: {user_msg}")
    if recovery:
        print(f"\n{recovery}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
