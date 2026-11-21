
from pathlib import Path
import shutil

from repositories.customer_repository import CustomerRepository
from repositories.trading_repository import TradingRepository


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

OLD_FILE = DATA_DIR / "customers.json"
NEW_FILE = DATA_DIR / "trading.json"
BACKUP_FILE = DATA_DIR / "customers_before_migration.json"


def main():
    if NEW_FILE.exists():
        customers, orders = TradingRepository(NEW_FILE).load()

        print("Trading database already exists.")
        print("No existing data was overwritten.")
        print(f"Customers: {len(customers)}")
        print(f"Orders: {len(orders)}")
        return

    if OLD_FILE.exists():
        customers = CustomerRepository(OLD_FILE).load()

        if BACKUP_FILE.exists():
            raise RuntimeError(
                "Backup already exists. Check it before continuing."
            )

        shutil.copy2(OLD_FILE, BACKUP_FILE)

        # Verify that the backup can also be read.
        CustomerRepository(BACKUP_FILE).load()

        print("Original customer database backed up.")
    else:
        customers = {}
        print("No previous customer database found.")

    repository = TradingRepository(NEW_FILE)
    repository.save(customers, {})

    restored_customers, restored_orders = repository.load()

    if (
        set(restored_customers) != set(customers)
        or restored_orders
    ):
        raise RuntimeError("Migration verification failed.")

    print("Migration successful!")
    print(f"Customers migrated: {len(restored_customers)}")
    print("Orders migrated: 0")
    print("Original customer data remains unchanged.")


if __name__ == "__main__":
    main()
