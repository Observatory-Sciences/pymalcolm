from malcolm.modules.builtin.defines import Define, AName, AStringValue, ADefine

from annotypes import add_call_types

# sigh.
@add_call_types
def to_lower(name: AName, value: AStringValue ) -> ADefine:
    return Define(name, value.lower())
