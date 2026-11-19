from _lib import write, filler, has_number, rng

PROMPT = ("Using the staff handbook in handbook/, how many days do I have to submit an expense claim for an overseas "
          "business trip? Give the number and the file that says so.")
KIND, SIZE, WEB = "everyday", "short", False

TOPICS = ("annual-leave sick-leave parental-leave remote-work equipment security passwords data-protection "
          "code-of-conduct grievances performance training probation overtime payroll pensions benefits health "
          "safety first-aid fire-drill visitors parking canteen dress-code social-media gifts conflicts whistleblowing "
          "recruitment onboarding offboarding references contracts holidays bereavement volunteering expenses "
          "travel procurement").split()

FACTS = {
    "travel": ["Domestic travel: expense claims must be submitted within 30 days of the trip.",
               "Overseas travel: expense claims must be submitted within 45 days of your return."],
    "expenses": ["General expense claims must be submitted within 60 days of purchase, unless a more specific "
                 "policy (for example travel.md) sets another limit."],
    "payroll": ["Claims approved after the 20th are paid with the following month's salary."],
}

def setup(d):
    r = rng(31)
    for topic in TOPICS:
        lines = [f"# {topic.replace('-', ' ').title()} policy", ""]
        for _ in range(20):
            lines += [f"## {r.choice(('Scope', 'Eligibility', 'Procedure', 'Exceptions', 'Approval', 'Records'))}",
                      *filler(r, 5), ""]
        for fact in FACTS.get(topic, []):
            lines.insert(r.randint(5, len(lines) - 1), fact)
        write(d, f"handbook/{topic}.md", "\n".join(lines) + "\n")

def check(d, answer):
    ok = has_number(answer, 45) and "travel" in answer.lower()
    return ok, "expected 45 days, from travel.md"
