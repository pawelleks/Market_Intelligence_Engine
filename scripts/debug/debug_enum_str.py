
from enum import Enum

class SecurityType(Enum):
    OPTION = "OPTION"
    STOCK = "STOCK"
    INDEX = "INDEX"

option = SecurityType.OPTION
stock = SecurityType.STOCK

print(f"Option Str: {str(option)}")
print(f"Stock Str: {str(stock)}")
print(f"Option Repr: {repr(option)}")

# Simulate the check logic
raw_sec_type = option
sec_type_str = str(raw_sec_type)
is_option = sec_type_str == "OPTION" or sec_type_str == "SecurityType.OPTION"
print(f"Is Option Detected? {is_option}")
