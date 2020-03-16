from collections import defaultdict
from obidog.databases import CppDatabase
from obidog.bindings.flavours import sol3 as flavour
from obidog.bindings.utils import strip_include
from obidog.bindings.classes import generate_classes_bindings
from obidog.bindings.enums import generate_enums_bindings
from obidog.bindings.functions import generate_functions_bindings
from obidog.bindings.globals import generate_globals_bindings
from obidog.logger import log
import os


BINDINGS_INCLUDE_TEMPLATE = """
#pragma once

namespace {state_view_forward_decl_ns} {{ class {state_view_forward_decl_cls}; }};
namespace {namespace}
{{
{bindings_functions_signatures}
}};
""".strip(
    "\n"
)

BINDINGS_SRC_TEMPLATE = """
#include <{bindings_header}>

{includes}

#include <{bindings_lib}>

namespace {namespace}
{{
{bindings_functions}
}};
""".strip(
    "\n"
)

OUTPUT_DIRECTORY = os.environ["OBENGINE_BINDINGS_OUTPUT"]


def group_bindings_by_namespace(cpp_db):
    group_by_namespace = defaultdict(CppDatabase)
    for item_type in [
        "classes",
        "enums",
        "functions",
        "globals",
        "typedefs",
    ]:
        for item_name, item_value in getattr(cpp_db, item_type).items():
            strip_template = item_name.split("<")[0]
            last_namespace = "::".join(strip_template.split("::")[:-1:])
            getattr(group_by_namespace[last_namespace], item_type)[
                item_name
            ] = item_value
    for namespace_name, namespace in group_by_namespace.items():
        namespace.namespaces = cpp_db.namespaces[namespace_name]
    return group_by_namespace


def make_bindings_header(path, namespace, objects):
    inc_out = os.path.join(OUTPUT_DIRECTORY, "include", "Core", path)
    state_view = flavour.STATE_VIEW
    bindings_functions = [
        f"void Load{object_name}({state_view} state);" for object_name in objects
    ]
    with open(inc_out, "w") as class_binding:
        class_binding.write(
            BINDINGS_INCLUDE_TEMPLATE.format(
                namespace=f"{namespace}::Bindings",
                bindings_functions_signatures="\n".join(
                    f"{binding_function}" for binding_function in bindings_functions
                ),
                state_view_forward_decl_ns="::".join(state_view.split("::")[:-1:]),
                state_view_forward_decl_cls=state_view.split("::")[-1],
            )
        )


def make_bindings_sources(namespace, path, bindings_header, *datasets):
    with open(path, "w") as bindings_source:
        all_includes = set(
            includes
            for data in datasets
            for includes in data["includes"]
            if not includes.endswith(".cpp")
        )
        all_functions = [
            functions for data in datasets for functions in data["bindings_functions"]
        ]
        bindings_source.write(
            BINDINGS_SRC_TEMPLATE.format(
                bindings_header=bindings_header,
                bindings_lib=flavour.INCLUDE_FILE,
                namespace=f"{namespace}::Bindings",
                includes="\n".join(all_includes),
                bindings_functions="\n".join(all_functions),
            )
        )


def generate_bindings_for_namespace(name, namespace):
    log.info(f"Generating bindings for namespace {name}")
    split_name = "/".join(name.split("::")[1::]) if "::" in name else name.capitalize()
    base_path = f"Bindings/{split_name}"
    os.makedirs(
        os.path.join(OUTPUT_DIRECTORY, "include", "Core", base_path), exist_ok=True
    )
    os.makedirs(os.path.join(OUTPUT_DIRECTORY, "src", "Core", base_path), exist_ok=True)
    class_bindings = generate_classes_bindings(namespace.classes)
    enum_bindings = generate_enums_bindings(name, namespace.enums)
    functions_bindings = generate_functions_bindings(namespace.functions)
    globals_bindings = generate_globals_bindings(name, namespace.globals)

    bindings_header = os.path.join(base_path, f"{name.split('::')[-1]}.hpp").replace(
        os.path.sep, "/"
    )

    generated_objects = (
        class_bindings["objects"]
        + enum_bindings["objects"]
        + functions_bindings["objects"]
        + globals_bindings["objects"]
    )

    make_bindings_header(bindings_header, name, generated_objects)
    namespace_data = {
        "includes": namespace.namespaces["additional_includes"]
        if "additional_includes" in namespace.namespaces
        else [],
        "bindings_functions": [],
    }
    src_out = os.path.join(
        OUTPUT_DIRECTORY, "src", "Core", base_path, f"{name.split('::')[-1]}.cpp"
    )
    make_bindings_sources(
        name,
        src_out,
        bindings_header,
        enum_bindings,
        class_bindings,
        functions_bindings,
        globals_bindings,
        namespace_data,
    )
    return generated_objects

def fetch_sub_dict(d, path):
    if len(path) == 0:
        return d
    if len(path) > 1:
        return fetch_sub_dict(d[path[0]], path[1::])
    else:
        return d[path[0]]

BINDTREE_NEWTABLE = "BindTree{fetch_table}.add(\"{last_table}\", InitTreeNodeAsTable(\"{intermediate_table}\"));"
def fix_index_tables(tables):
    # Pre-sort the table to fix missing intermediate tables
    tables.sort(key=lambda x: x.count("["))
    table_tree = {}
    for table in tables:
        table_path = table.split("InitTreeNodeAsTable(\"")[1].replace("\"));", "").split(".")
        for i, elem in enumerate(table_path):
            if not elem in fetch_sub_dict(table_tree, table_path[:i]):
                if i != len(table_path) - 1:
                    print("Add missing intermediate table")
                    tables.append(BINDTREE_NEWTABLE.format(
                        fetch_table="".join([f"[\"{item}\"]" for item in table_path[:i]]),
                        last_table=table_path[i],
                        intermediate_table=".".join(table_path[:i + 1])
                    ))
                fetch_sub_dict(table_tree, table_path[:i])[table_path[i]] = {}
    # Don't load a sub-table before the main one
    tables.sort(key=lambda x: x.count("["))


# LATER: Generate bindings shorthands
def generated_bindings_index(generated_objects):
    print("Generating Bindings Index...")
    body = []
    include_list = []
    for current_dir, folders, files in os.walk(
        os.path.join(OUTPUT_DIRECTORY, "include/Core/Bindings")
    ):
        for f in files:
            if f.endswith(".hpp"):
                fp = (
                    os.path.join(current_dir, f)
                    .split(OUTPUT_DIRECTORY)[1]
                    .lstrip("/\\")
                )
                include_list.append(strip_include(fp).replace("\\", "/"))
    body += [f"#include <{path}>" for path in include_list]
    body += [
        f"#include <{flavour.INCLUDE_FILE}>",
        "namespace obe::Bindings {",
        f"void IndexAllBindings({flavour.STATE_VIEW} state)\n{{",
        'BindingTree BindTree("ObEngine");',
        'BindTree.add("obe", InitTreeNodeAsTable("obe"));',
    ]
    tables = []
    bindings = []
    for namespace_name, objects in generated_objects.items():
        ns_split = namespace_name.split("::")
        namespace_path = "".join(
            f'["{namespace_part}"]' for namespace_part in ns_split[:-1]
        )
        namespace_full_path = "".join(
            f'["{namespace_part}"]' for namespace_part in ns_split
        )
        namespace_dotted = ".".join(ns_split)
        namespace_last_name = ns_split[-1]
        tables.append(
            f'BindTree{namespace_path}.add("{namespace_last_name}", InitTreeNodeAsTable("{namespace_dotted}"));'
        )
        print(objects)
        bindings.append(f"BindTree{namespace_full_path}")
        for generated_object in objects:
            bindings.append(
                f'.add("{generated_object}", &{namespace_name}::Bindings::Load{generated_object})'
            )
        bindings[-1] = bindings[-1] + ";"
        bindings.append("\n")
    fix_index_tables(tables)
    body += tables
    body += bindings
    body.append("BindTree(state);")
    body.append("}}")
    return "\n".join(body)


# LATER: Add a tag in Doxygen to allow custom name / namespace binding
# LATER: Add a tag in Doxygen to list possible templated types
# LATER: Add a tag in Doxygen to make fields privates
# TODO: Add a tag in Doxygen to specify a helper script
# OR add a way to define a list of helpers (lua scripts) to run for some namespaces
# TODO: Check if it's possible to change a bound global value from Lua, otherwise provide a lambda setter
# LATER: Provide a way to "patch" some namespaces / classes / functions with callbacks
# LATER: Provide a "policy" system to manage bindings grouping etc...
# LATER: Try to shorten function pointers / full names given the namespace we are in while binding
# TODO: Check behaviour with std::optional, std::variant, std::any (getSegmentContainingPoint for example)
# TODO: Check behaviour with smart pointers
# TODO: Allow injection of "commonly used types" in templated functions using a certain flag in doc (pushParameter for example)
def generate_bindings(cpp_db):
    log.info("===== Generating bindings for ÖbEngine ====")
    namespaces = group_bindings_by_namespace(cpp_db)
    generated_objects = {}
    for namespace_name, namespace in namespaces.items():
        generated_objects[namespace_name] = generate_bindings_for_namespace(
            namespace_name, namespace
        )
    with open(
        os.path.join(OUTPUT_DIRECTORY, "src/Core/Bindings/index.cpp"), "w"
    ) as bindings_index:
        bindings_index.write(generated_bindings_index(generated_objects))
    print("STOP")
