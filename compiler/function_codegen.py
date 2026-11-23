"""Compile scoped, typed u32/u64 function statements to native C.

One checked AST drives both kernel and Linux targets. Functions cannot use
global state or I/O; every variable binding resolves to a unique C local.
"""
from __future__ import annotations

from collections import Counter

if __package__:
    from .language import (
        FunctionDef, MAX_FUNCTION_DEPTH, MAX_RUNTIME_STEPS,
        expression, fail, validate_name, array_code, array_details,
    )
    from .numeric_types import c_type
else:
    from language import (
        FunctionDef, MAX_FUNCTION_DEPTH, MAX_RUNTIME_STEPS,
        expression, fail, validate_name, array_code, array_details,
    )
    from numeric_types import c_type


def compile_functions(functions: dict[str, FunctionDef]) -> tuple[list[str], dict[str, int]]:
    lines: list[str] = []
    own_steps: dict[str, int] = {}
    edges: dict[str, Counter[str]] = {}

    for fn in functions.values():
        params = ", ".join(
            f"{c_type(fn.param_types.get(arg, 'u64'))} htmlk_{arg}"
            for arg in fn.params
        ) or "void"
        result_type = c_type(fn.return_type)
        lines.append(f"{result_type} htmlk_fn_{fn.name}({params});")

    for fn in functions.values():
        params = ", ".join(
            f"{c_type(fn.param_types.get(arg, 'u64'))} htmlk_{arg}"
            for arg in fn.params
        ) or "void"
        result_type = c_type(fn.return_type)
        code = [f"{result_type} htmlk_fn_{fn.name}({params}) {{"]
        # Unused parameters are legal, even when GCC uses -Wextra -Werror.
        for param in fn.params:
            code.append(f"  (void)htmlk_{param};")
        scopes: list[dict[str, str]] = [
            {arg: f"htmlk_{arg}" for arg in fn.params}
        ]
        type_scopes: list[dict[str, str]] = [
            {arg: fn.param_types.get(arg, "u64") for arg in fn.params}
        ]
        counts: Counter[str] = Counter()
        referenced: set[str] = set()
        bindings = 0
        loops = 0
        body_steps = 0

        def resolve() -> dict[str, str]:
            merged = {}
            for scope in scopes:
                merged.update(scope)
            return merged

        def resolve_types() -> dict[str, str]:
            merged = {}
            for scope in type_scopes:
                merged.update(scope)
            return merged

        def emit(nodes: list, indent: int, weight: int) -> None:
            nonlocal bindings, loops, body_steps
            pad = "  " * indent
            for node in nodes:
                body_steps += weight
                if body_steps > MAX_RUNTIME_STEPS:
                    fail(node, "function statement work budget exceeded")

                def checked(expr: str, *, boolean: bool = False,
                            expected_type: str | None = None,
                            evaluations: int = 1) -> str:
                    called: list[str] = []
                    value = expression(expr, node, resolve(), boolean=boolean,
                                       functions=functions, calls=called,
                                       variable_types=resolve_types(),
                                       expected_type=expected_type)
                    for callee in called:
                        counts[callee] += weight * evaluations
                        referenced.add(callee)
                    return value

                if node.tag == "let":
                    name = validate_name(node)
                    if name in scopes[-1]:
                        fail(node, f"variable {name!r} already declared in this scope")
                    typ = node.attrs["type"]
                    value = checked(node.attrs["value"], expected_type=typ)  # before binding
                    symbol = f"htmlk_local_{fn.name}_{bindings}"
                    bindings += 1
                    scopes[-1][name] = symbol
                    type_scopes[-1][name] = typ
                    ctype = c_type(typ)
                    code.extend((f"{pad}{ctype} {symbol} = {value};",
                                 f"{pad}(void){symbol};"))
                elif node.tag == "array":
                    name = validate_name(node)
                    if name in scopes[-1]:
                        fail(node, f"variable {name!r} already declared in this scope")
                    typ = node.attrs["type"]
                    size = int(node.attrs["length"])
                    symbol = f"htmlk_local_{fn.name}_{bindings}"
                    bindings += 1
                    scopes[-1][name] = symbol
                    type_scopes[-1][name] = array_code(typ, size)
                    code.extend((f"{pad}{c_type(typ)} {symbol}[{size}] = {{0}};",
                                 f"{pad}(void){symbol};"))
                elif node.tag == "store":
                    name = validate_name(node)
                    detail = array_details(resolve_types().get(name, ""))
                    if detail is None:
                        fail(node, f"undefined array {name!r}; declare <array> first")
                    element, _ = detail
                    location = checked(f"{name}[{node.attrs['index']}]", expected_type=element)
                    value = checked(node.attrs["value"], expected_type=element)
                    code.append(f"{pad}{location} = {value};")
                elif node.tag == "set":
                    name = validate_name(node)
                    variables = resolve()
                    if name not in variables:
                        fail(node, f"undefined variable {name!r}")
                    code.append(f"{pad}{variables[name]} = "
                                f"{checked(node.attrs['value'], expected_type=resolve_types()[name])};")
                elif node.tag == "if":
                    condition = checked(node.attrs["test"], boolean=True)
                    alternate = (node.children[-1] if node.children and
                                 node.children[-1].tag == "else" else None)
                    true_body = node.children[:-1] if alternate else node.children
                    code.append(f"{pad}if ({condition}) {{")
                    scopes.append({})
                    type_scopes.append({})
                    emit(true_body, indent + 1, weight)
                    scopes.pop()
                    type_scopes.pop()
                    if alternate is not None:
                        code.append(f"{pad}}} else {{")
                        scopes.append({})
                        type_scopes.append({})
                        emit(alternate.children, indent + 1, weight)
                        scopes.pop()
                        type_scopes.pop()
                    code.append(f"{pad}}}")
                elif node.tag == "repeat":
                    count = int(node.attrs["times"])
                    loop = f"htmlk_repeat_{fn.name}_{loops}"
                    loops += 1
                    code.append(f"{pad}for (uint64_t {loop} = 0;"
                                f" {loop} < UINT64_C({count}); ++{loop}) {{")
                    scopes.append({})
                    type_scopes.append({})
                    emit(node.children, indent + 1, weight * count)
                    scopes.pop()
                    type_scopes.pop()
                    code.append(f"{pad}}}")
                elif node.tag == "while":
                    count = int(node.attrs["max"])
                    condition = checked(node.attrs["test"], boolean=True,
                                        evaluations=count)
                    body_steps += weight * count  # guard evaluations
                    if body_steps > MAX_RUNTIME_STEPS:
                        fail(node, "function statement work budget exceeded")
                    loop = f"htmlk_repeat_{fn.name}_{loops}"
                    loops += 1
                    code.append(f"{pad}for (uint64_t {loop} = 0;"
                                f" {loop} < UINT64_C({count}) && ({condition}); ++{loop}) {{")
                    scopes.append({})
                    type_scopes.append({})
                    emit(node.children, indent + 1, weight * count)
                    scopes.pop()
                    type_scopes.pop()
                    code.append(f"{pad}}}")
                elif node.tag == "return":
                    code.append(f"{pad}return "
                                f"{checked(node.attrs['value'], expected_type=fn.return_type)};")
                elif node.tag == "break":
                    code.append(f"{pad}break;")
                elif node.tag == "continue":
                    code.append(f"{pad}continue;")
                else:
                    fail(node, f"unsupported statement <{node.tag}> inside function")
        emit(fn.body, 1, 1)
        code.append("}")
        lines.extend(code)
        own_steps[fn.name] = body_steps
        # Keep zero-trip loop references for static cycle/depth analysis.
        for call in referenced:
            counts.setdefault(call, 0)
        edges[fn.name] = counts

    costs: dict[str, tuple[int, int]] = {}

    def visit(name: str, chain: tuple[str, ...] = ()) -> tuple[int, int]:
        if name in chain:
            fail(functions[name].source_node,
                 "recursive function calls: " + " -> ".join((*chain, name)))
        if name not in costs:
            children = {child: visit(child, (*chain, name)) for child in edges[name]}
            depth = 1 + max((height for _, height in children.values()), default=0)
            steps = own_steps[name] + sum(
                edges[name][child] * children[child][0] for child in children
            )
            if steps > MAX_RUNTIME_STEPS:
                fail(functions[name].source_node, "function invocation work limit exceeded")
            costs[name] = (steps, depth)
        if len(chain) + costs[name][1] > MAX_FUNCTION_DEPTH:
            fail(functions[name].source_node,
                 f"function call depth exceeds {MAX_FUNCTION_DEPTH}")
        return costs[name]

    for name in functions:
        visit(name)
    return lines, {name: steps for name, (steps, _) in costs.items()}
