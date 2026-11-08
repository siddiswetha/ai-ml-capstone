"""Generate synthetic support-ticket data for the capstone.

All tickets are invented. No real customer data, no real company data.
Deterministic: same seed gives the same files every run.
"""
import csv
import random

random.seed(42)

PRODUCTS = ["desk lamp", "coffee maker", "headphones", "backpack", "water bottle",
            "keyboard", "desk chair", "phone charger", "blender", "notebook set"]

# (category, priority, [template, ...]) — each template takes a product name.
TEMPLATES = {
    "billing": ("high", [
        "I was charged twice for my {p} this month, please fix the duplicate charge",
        "My card was charged the wrong amount for the {p} order",
        "The invoice for my {p} shows a charge I do not recognise",
        "I paid for the {p} but my bill still says payment is due",
        "Please explain the extra fee on my {p} bill",
    ]),
    "access": ("high", [
        "I cannot log in to my account to check my {p} order",
        "My password reset link for the {p} account is not working",
        "I am locked out of my account after trying to view my {p} order",
        "The sign in page keeps saying my password is wrong for my {p} account",
        "I lost access to the email linked to my {p} order and cannot log in",
    ]),
    "delivery": ("medium", [
        "My {p} has not arrived yet and the tracking has not moved in days",
        "The delivery of my {p} is late, can you check the shipment status",
        "My {p} package says delivered but I never received it",
        "Please tell me when my {p} order will arrive, the tracking page is blank",
        "The courier left my {p} at the wrong address",
    ]),
    "defect": ("high", [
        "My {p} arrived broken and does not turn on at all",
        "The {p} I received is cracked and faulty, it stopped working after one day",
        "My {p} is damaged, the screen is scratched and the button is stuck",
        "The {p} makes a strange noise and does not work properly",
        "I received a defective {p} with a missing part",
    ]),
    "refund": ("medium", [
        "I would like a refund for my {p} because I no longer need it",
        "Please return my money for the {p}, I have sent it back",
        "I cancelled my {p} order but I have not received my refund yet",
        "How do I get a refund for the faulty {p} I returned last week",
        "The refund for my {p} has not arrived after ten days",
    ]),
    "account": ("low", [
        "Please change the email address on my account for my {p} order",
        "I need to update my delivery address for my {p} order",
        "Can you change the name on my account, I use it for my {p} orders",
        "I would like to close my account, I no longer order the {p}",
        "Please update my phone number on my profile for {p} delivery updates",
    ]),
}


def build_rows():
    rows = []
    for category, (priority, templates) in TEMPLATES.items():
        for i, template in enumerate(templates):
            for variant in range(4):
                product = PRODUCTS[(i * 4 + variant) % len(PRODUCTS)]
                text = template.format(p=product)
                if variant == 1:
                    text = text + " please help"
                elif variant == 2:
                    text = "Hello, " + text
                elif variant == 3:
                    text = text + " thank you"
                rows.append((text, category, priority))
    random.shuffle(rows)
    return rows


def main():
    rows = build_rows()  # 6 categories * 5 templates * 4 variants = 120
    train, test = rows[:90], rows[90:]
    for path, subset in (("data/tickets_train.csv", train),
                         ("data/tickets_test.csv", test)):
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["text", "category", "priority"])
            writer.writerows(subset)
        print(path, len(subset), "rows")


if __name__ == "__main__":
    main()
