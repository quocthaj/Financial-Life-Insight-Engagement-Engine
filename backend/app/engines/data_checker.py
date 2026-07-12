from app.models.schemas import CustomerFullProfile, DataAvailabilityReport


REQUIRED_GROUPS_FOR_OBSERVATIONS = [
    "profile",
    "transactions",
    "savings",
    "borrowings",
    "investments",
]

REQUIRED_GROUPS_FOR_PRODUCT_NUDGES = [
    "profile",
    "transactions",
    "savings",
    "borrowings",
    "app_usage",
]


def check_data_availability(customer: CustomerFullProfile) -> DataAvailabilityReport:
    available = []
    missing = []
    notes = []

    if customer.profile:
        available.append("profile")
    else:
        missing.append("profile")

    if len(customer.transactions) > 0:
        available.append("transactions")
    else:
        missing.append("transactions")

    if len(customer.savings) > 0:
        available.append("savings")
    else:
        missing.append("savings")

    if len(customer.borrowings) > 0:
        available.append("borrowings")
    else:
        notes.append("No borrowing records available for this customer.")

    if len(customer.investments) > 0:
        available.append("investments")
    else:
        notes.append("No investment holding records available for this customer. Note: Missing investment holdings enables dormant_feature detection specifically.")

    if len(customer.app_usage) > 0:
        available.append("app_usage")
    else:
        missing.append("app_usage")

    can_generate_financial_observations = all(
        group in available or group in ["borrowings", "investments"]
        for group in REQUIRED_GROUPS_FOR_OBSERVATIONS
    )

    can_generate_product_nudges = all(
        group in available for group in REQUIRED_GROUPS_FOR_PRODUCT_NUDGES
    )

    return DataAvailabilityReport(
        customer_id=customer.profile.customer_id,
        available_data_groups=available,
        missing_data_groups=missing,
        can_generate_financial_observations=can_generate_financial_observations,
        can_generate_product_nudges=can_generate_product_nudges,
        notes=notes,
    )
