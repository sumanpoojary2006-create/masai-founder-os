"""CLI entrypoint for the AI Company Simulator."""

try:
    from ai_company.config import APP_NAME, EXIT_COMMANDS, LOGGER
    from ai_company.core.memory import MemoryStore
    from ai_company.core.router import TaskRouter
except ImportError:
    from config import APP_NAME, EXIT_COMMANDS, LOGGER
    from core.memory import MemoryStore
    from core.router import TaskRouter


def print_banner() -> None:
    """Show a short welcome message for CLI users."""
    print("=" * 60)
    print(f"{APP_NAME}")
    print("Type a Masai business task and the simulator will route it.")
    print(f"Exit anytime with: {', '.join(sorted(EXIT_COMMANDS))}")
    print("=" * 60)


def main() -> None:
    """Run a simple REPL loop for the simulator."""
    memory = MemoryStore()
    router = TaskRouter()

    print_banner()

    while True:
        user_input = input("\nTask> ").strip()

        if not user_input:
            print("Please enter a Masai task for the founder desk.")
            continue

        if user_input.lower() in EXIT_COMMANDS:
            print("\nSession ended. Thanks for using the simulator.")
            break

        LOGGER.info("Received new task from user")
        result = router.handle_task(user_input)
        memory.add_entry(
            task=user_input,
            response=result["response"],
            department=result["department"],
            route_reason=result["manager_reason"],
        )

        print("\nDepartment:", result["department"].title())
        print("Manager Reason:", result["manager_reason"])
        print("Response:")
        print(result["response"])


if __name__ == "__main__":
    main()
