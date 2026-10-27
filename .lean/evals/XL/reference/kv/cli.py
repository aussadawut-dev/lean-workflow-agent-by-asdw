"""Command line: main(argv, store) -> (exit code, output text)."""


def main(argv, store):
    if not argv:
        return 2, "error: no command"
    command, args = argv[0], argv[1:]
    if command == "set" and len(args) in (2, 4) and (len(args) == 2 or args[2] == "--ttl"):
        ttl = None
        if len(args) == 4:
            try:
                ttl = float(args[3])
                store.set(args[0], args[1], ttl=ttl)
            except ValueError:
                return 2, f"error: invalid ttl {args[3]!r}"
            return 0, "OK"
        store.set(args[0], args[1])
        return 0, "OK"
    if command == "get" and len(args) == 1:
        value = store.get(args[0])
        return (0, value) if value is not None else (1, "(nil)")
    if command == "delete" and len(args) == 1:
        return 0, "1" if store.delete(args[0]) else "0"
    if command == "keys" and not args:
        return 0, "\n".join(store.keys())
    if command == "ttl" and len(args) == 1:
        return 0, str(store.ttl(args[0]))
    return 2, f"error: bad command {command!r}"
