import os

from obidog.bindings.utils import strip_include
import obidog.bindings.flavours.sol3 as flavour
from obidog.utils.string_utils import format_name
from obidog.bindings.utils import fetch_table, get_include_file
from obidog.logger import log
import inflection


def generate_globals_bindings(name, cpp_globals):
    includes = []
    bindings_functions = []
    objects = []
    for global_name, cpp_global in cpp_globals.items():
        if cpp_global.flags.nobind:
            continue
        export_name = format_name(cpp_global.name)
        log.info(f"  Generating bindings for global {global_name}")
        includes.append(get_include_file(cpp_global))
        objects.append(
            {
                "bindings": f"Global{export_name}",
                "identifier": f"{cpp_global.namespace}::{cpp_global.name}",
            }
        )
        state_view = flavour.STATE_VIEW
        binding_function_signature = f"void LoadGlobal{export_name}({state_view} state)"
        namespace_access = fetch_table(name) + "\n"
        binding_function_body = namespace_access + flavour.GLOBAL_BODY.format(
            namespace=name.split("::")[-1],
            global_name=cpp_global.name,
            global_ptr=global_name,
        )
        bindings_functions.append(
            f"{binding_function_signature}\n{{\n" f"{binding_function_body}\n}}"
        )
    return {
        "includes": includes,
        "bindings_functions": bindings_functions,
        "objects": objects,
    }
