"""
Single source of truth for skills.

- SKILL_CATEGORIES: every skill belongs to a short category description.
- SKILL_VOCAB:      the canonical skills the extractor can recognise.
- ALIASES:          official alternate names, mapped to the canonical name.
- SKILL_CONTEXT:    "category: skill" text used to embed skills for similarity.

Bare skill names embed poorly (e.g. "FastAPI" vs "Flask" scores 0.23, while
"Docker" vs "Photoshop" scores 0.27). Embedding "Python web framework: Flask"
instead separates related skills (0.58-0.77) from unrelated ones (<0.25).
"""

SKILL_CATEGORIES = {
    "programming language": [
        "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Go", "Rust",
        "Ruby", "PHP", "R", "Kotlin", "Swift", "Bash",
    ],
    "Python web framework": ["Django", "Flask", "FastAPI", "Pyramid", "Tornado", "Bottle"],
    "JavaScript backend framework": ["Node.js", "Express", "NestJS"],
    "JavaScript frontend framework": ["React", "Vue", "Angular", "Svelte", "Next.js", "Nuxt"],
    "Java web framework": ["Spring Boot"],
    "web markup and styling": ["HTML", "CSS"],
    "relational database": ["SQL", "MySQL", "PostgreSQL"],
    "NoSQL database": ["MongoDB", "Redis", "Cassandra", "DynamoDB", "Firebase"],
    "search engine": ["ElasticSearch"],
    "data warehouse": ["Snowflake"],
    "cloud platform": ["AWS", "GCP", "Azure", "DigitalOcean", "Heroku"],
    "AWS cloud service": ["EC2", "S3", "Lambda", "RDS", "CloudFront", "Route53", "IAM"],
    "container tool": ["Docker", "Docker-Compose"],
    "container orchestration tool": ["Kubernetes", "Helm", "OpenShift"],
    "infrastructure as code tool": ["Terraform", "CloudFormation", "Ansible", "Chef", "Puppet"],
    "CI/CD tool": ["Jenkins", "GitHub Actions", "GitLab CI", "CircleCI", "Travis CI", "ArgoCD", "CI/CD"],
    "big data processing framework": ["Spark", "Hadoop", "Hive", "Pig"],
    "messaging and streaming system": ["Kafka", "RabbitMQ", "Message Queue"],
    "workflow and ML operations tool": ["Airflow", "MLflow"],
    "machine learning framework": ["TensorFlow", "PyTorch", "scikit-learn", "Hugging Face"],
    "data analysis library": ["Pandas", "NumPy", "Matplotlib"],
    "API style": ["REST APIs", "GraphQL", "gRPC", "SOAP", "WebSocket"],
    "software architecture pattern": ["Microservices", "Serverless", "Monolithic", "Event-Driven"],
    "version control tool": ["Git", "GitHub", "GitLab", "Bitbucket"],
    "operating system": ["Linux", "Unix", "Windows"],
    "agile project methodology": ["Agile", "Scrum", "Kanban"],
    "project tracking tool": ["JIRA", "Confluence"],
    "UI design tool": ["Figma", "Sketch", "Adobe XD", "Material Design"],
    "image editing tool": ["Photoshop", "Illustrator"],
    "business intelligence tool": ["Tableau", "Power BI", "Looker"],
    "spreadsheet tool": ["Excel"],
    "monitoring tool": ["Prometheus", "Grafana"],
    "Android development framework": ["Jetpack Compose", "Android SDK"],
}

# Official alternate names -> canonical skill
ALIASES = {
    "Amazon Web Services": "AWS",
    "Microsoft Azure": "Azure",
    "Google Cloud": "GCP",
    "Jira": "JIRA",
    "REST API": "REST APIs",
    "Apache Airflow": "Airflow",
    "Elasticsearch": "ElasticSearch",
}

SKILL_VOCAB = [s for skills in SKILL_CATEGORIES.values() for s in skills]

# {"Flask": "Python web framework: Flask", ...}
SKILL_CONTEXT = {
    skill: f"{category}: {skill}"
    for category, skills in SKILL_CATEGORIES.items()
    for skill in skills
}


def canonical(skill):
    """Map an alias to its canonical skill name (unchanged if not an alias)."""
    return ALIASES.get(skill, skill)
