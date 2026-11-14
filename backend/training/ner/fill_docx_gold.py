"""Fill gold labels for the 100 template DOCX resumes straight from their text.

These resumes come from one template: "<Name> - Resume", a "Skills" line, two fixed
jobs and one fixed degree. The labels are read from the document text (not from a
parser), so they are ground truth for what the file says. experience_years is left
empty on purpose: dates run to "Present", so the answer depends on the year.

Only files whose label is still blank (no labeller) are filled.
"""

import json
import re
from pathlib import Path

GOLD = Path(__file__).parent / "gold"
PATTERN = re.compile(r"^[a-z]+_[a-z]+_\d+\.txt$")


def main() -> None:
    done = 0
    for txt in sorted(GOLD.glob("*.txt")):
        if not PATTERN.match(txt.name):
            continue
        label_path = txt.with_suffix(".json")
        label = json.loads(label_path.read_text(encoding="utf-8"))
        if label.get("labeller"):
            continue
        text = txt.read_text(encoding="utf-8")
        name = text.splitlines()[0].replace(" - Resume", "").strip()
        skills_line = re.search(r"\nSkills\n(.+)\n", text).group(1)
        label.update({
            "labeller": "derived-from-template",
            "name": name,
            "skills": [s.strip() for s in skills_line.split(",") if s.strip()],
            "degree": "Bachelor's Degree",  # "B.S. in Computer Science"
            "job_titles": ["Senior Software Engineer", "Software Engineer"],
            "companies": ["Tech Corp", "Startup Inc"],
            "notes": "Template resume. experience_years deliberately not labelled.",
        })
        label.pop("_instructions", None)
        label_path.write_text(json.dumps(label, indent=2), encoding="utf-8")
        done += 1
    print(f"filled {done} template resumes")


if __name__ == "__main__":
    main()
