"""
Skills Gazetteer
-----------------
A curated list of technical and soft skills used for rule-based skill
extraction, layered on top of spaCy NER.

Design note (see project documentation, Section 5.1):
  A pure statistical NER model frequently misses domain-specific skill
  tokens (e.g. "Kubernetes", "Scrum", "P&L ownership") because they never
  appeared often enough in the model's general-purpose training data.
  A gazetteer (curated term list) closes that gap and is the standard,
  cheap technique used in production resume-parsing systems.

This starter list covers ~180 terms across the role categories present in
the organizer-provided dataset (Full Stack Developer, Business Analyst,
Project Manager, Software Engineer). Expand this list as you discover more
skills while testing against the full 228-resume dataset -- see
scripts/mine_candidate_skills.py for a helper that suggests new candidate
terms from the dataset itself.
"""

# Canonical skill -> set of surface-form aliases seen in real resumes.
# Keys are the *canonical* skill name shown in the UI / explainability layer.
SKILLS_GAZETTEER = {
    # ─────────────────────────────────────────────────────────────
    # PROGRAMMING LANGUAGES
    # ─────────────────────────────────────────────────────────────
    "Python": ["python", "python3", "python 3", "py"],
    "Java": ["java", "java8", "java 8", "j2ee", "java ee", "core java"],
    "JavaScript": ["javascript", "js", "es6", "es2015", "ecmascript", "vanilla js"],
    "TypeScript": ["typescript", "ts"],
    "C#": ["c#", "c sharp", "csharp"],
    "C++": ["c++", "cpp", "c plus plus"],
    "C": ["c programming", "c language"],
    "PHP": ["php", "php7", "php8"],
    "Ruby": ["ruby", "ruby on rails", "rails"],
    "Swift": ["swift", "swiftui"],
    "Kotlin": ["kotlin"],
    "Dart": ["dart", "flutter"],
    "Rust": ["rust"],
    "Go": ["golang", " go "],
    "Scala": ["scala"],
    "R": ["r programming", " r "],
    "MATLAB": ["matlab"],
    "Shell Scripting": ["bash", "shell script", "shell scripting", "bash scripting", "powershell", "zsh"],
    "VBA": ["vba", "visual basic for applications", "visual basic"],

    # ─────────────────────────────────────────────────────────────
    # WEB / FRONTEND
    # ─────────────────────────────────────────────────────────────
    "React": ["react", "reactjs", "react.js", "react js"],
    "Next.js": ["next.js", "nextjs", "next js"],
    "Angular": ["angular", "angularjs", "angular.js", "angular 2+"],
    "Vue.js": ["vue", "vuejs", "vue.js", "nuxt", "nuxtjs"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3", "sass", "scss", "less"],
    "Tailwind CSS": ["tailwind", "tailwindcss", "tailwind css"],
    "Bootstrap": ["bootstrap"],
    "jQuery": ["jquery", "jquery.js"],
    "Redux": ["redux", "redux toolkit", "react redux", "zustand", "mobx"],
    "Node.js": ["node", "nodejs", "node.js"],
    "Express.js": ["express", "expressjs", "express.js"],
    "REST APIs": ["rest", "restful", "rest api", "restful api", "restful web services", "rest apis", "web services"],
    "GraphQL": ["graphql"],
    "WebSockets": ["websocket", "websockets", "socket.io"],

    # ─────────────────────────────────────────────────────────────
    # BACKEND / FRAMEWORKS
    # ─────────────────────────────────────────────────────────────
    "Spring": ["spring", "spring boot", "spring mvc", "spring framework", "spring cloud"],
    "Django": ["django", "django rest framework", "drf"],
    "Flask": ["flask"],
    "FastAPI": ["fastapi", "fast api"],
    "Laravel": ["laravel"],
    "ASP.NET": [".net", "dotnet", "asp.net", "asp .net", ".net core", "dotnet core"],
    "Hibernate": ["hibernate", "hibernate orm"],
    "Microservices": ["microservices", "micro-services", "microservice architecture"],
    "GraphQL": ["graphql"],

    # ─────────────────────────────────────────────────────────────
    # MOBILE
    # ─────────────────────────────────────────────────────────────
    "Flutter": ["flutter"],
    "React Native": ["react native", "react-native"],
    "Android Development": ["android", "android development", "android studio"],
    "iOS Development": ["ios", "ios development", "xcode"],

    # ─────────────────────────────────────────────────────────────
    # CLOUD / DEVOPS
    # ─────────────────────────────────────────────────────────────
    "AWS": ["aws", "amazon web services", "ec2", "s3", "lambda", "aws lambda", "cloudwatch", "rds", "dynamodb"],
    "Azure": ["azure", "microsoft azure", "azure devops"],
    "GCP": ["gcp", "google cloud", "google cloud platform"],
    "Docker": ["docker", "containerization", "container"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Jenkins": ["jenkins", "ci/cd", "continuous integration", "continuous deployment", "github actions", "gitlab ci"],
    "Terraform": ["terraform", "infrastructure as code", "iac"],
    "Git": ["git", "github", "gitlab", "bitbucket", "version control", "git flow"],
    "Linux": ["linux", "ubuntu", "centos", "debian", "unix"],
    "Nginx": ["nginx"],
    "Apache": ["apache", "apache tomcat", "tomcat"],

    # ─────────────────────────────────────────────────────────────
    # DATABASES
    # ─────────────────────────────────────────────────────────────
    "SQL": ["sql", "t-sql", "pl/sql", "plsql"],
    "MySQL": ["mysql", "my sql"],
    "PostgreSQL": ["postgresql", "postgres", "pgsql"],
    "SQL Server": ["sql server", "mssql", "ms sql", "microsoft sql server"],
    "Oracle": ["oracle", "oracle db", "oracle database"],
    "MongoDB": ["mongodb", "mongo db", "mongo"],
    "Firebase": ["firebase", "firestore", "firebase realtime database"],
    "Redis": ["redis"],
    "SQLite": ["sqlite"],
    "Supabase": ["supabase"],
    "Elasticsearch": ["elasticsearch", "elastic search", "elk"],
    "Cassandra": ["cassandra", "apache cassandra"],
    "Data Warehousing": ["data warehouse", "data warehousing", "etl", "informatica", "ssis", "data pipeline"],

    # ─────────────────────────────────────────────────────────────
    # DATA SCIENCE / AI / ML
    # ─────────────────────────────────────────────────────────────
    "Machine Learning": ["machine learning", "ml model", "scikit-learn", "sklearn", "supervised learning", "unsupervised learning"],
    "Deep Learning": ["deep learning", "neural network", "cnn", "rnn", "lstm"],
    "NLP": ["nlp", "natural language processing", "text mining", "sentiment analysis"],
    "TensorFlow": ["tensorflow", "tensor flow", "tf"],
    "PyTorch": ["pytorch", "torch"],
    "Pandas": ["pandas", "pandas library"],
    "NumPy": ["numpy", "num py"],
    "Matplotlib": ["matplotlib", "seaborn", "data visualization"],
    "Computer Vision": ["computer vision", "opencv", "cv2", "image processing"],
    "Tableau": ["tableau"],
    "Power BI": ["power bi", "powerbi", "microsoft power bi"],
    "Big Data": ["big data", "hadoop", "spark", "apache spark", "hive", "kafka", "apache kafka"],
    "Data Analysis": ["data analysis", "data analytics", "statistical analysis"],
    "Statistics": ["statistics", "statistical modeling", "regression", "hypothesis testing"],

    # ─────────────────────────────────────────────────────────────
    # MICROSOFT OFFICE (very common in Pakistani CVs)
    # ─────────────────────────────────────────────────────────────
    "MS Excel": ["excel", "ms excel", "microsoft excel", "advanced excel", "excel pivot", "vlookup", "pivot tables"],
    "MS Word": ["ms word", "microsoft word", "word processing"],
    "MS PowerPoint": ["powerpoint", "ms powerpoint", "microsoft powerpoint", "presentations"],
    "MS Office": ["ms office", "microsoft office", "office suite", "ms office suite", "office 365", "microsoft 365"],
    "MS Access": ["ms access", "microsoft access", "access database"],
    "MS Project": ["ms project", "microsoft project"],
    "SharePoint": ["sharepoint", "microsoft sharepoint"],
    "Outlook": ["outlook", "ms outlook"],

    # ─────────────────────────────────────────────────────────────
    # DESIGN / UI/UX
    # ─────────────────────────────────────────────────────────────
    "Figma": ["figma"],
    "Adobe XD": ["adobe xd", "xd"],
    "UI/UX Design": ["ui/ux", "ui ux", "user interface design", "user experience design", "ux design", "ui design"],
    "Photoshop": ["photoshop", "adobe photoshop"],
    "Illustrator": ["illustrator", "adobe illustrator"],
    "Canva": ["canva"],
    "Wireframing": ["wireframe", "wireframing", "mockup", "prototyping"],

    # ─────────────────────────────────────────────────────────────
    # QA / TESTING
    # ─────────────────────────────────────────────────────────────
    "JUnit": ["junit", "unit testing", "testng"],
    "Selenium": ["selenium", "test automation", "automated testing"],
    "Postman": ["postman"],
    "Swagger": ["swagger", "openapi", "api documentation"],
    "SoapUI": ["soapui"],
    "Manual Testing": ["manual testing", "qa testing", "quality assurance", "functional testing"],
    "Performance Testing": ["performance testing", "load testing", "jmeter"],
    "Regression Testing": ["regression testing", "regression"],
    "Cypress": ["cypress"],
    "Jest": ["jest"],

    # ─────────────────────────────────────────────────────────────
    # BUSINESS ANALYSIS
    # ─────────────────────────────────────────────────────────────
    "Requirements Gathering": ["requirements gathering", "requirement analysis", "business requirements", "requirement elicitation"],
    "Stakeholder Management": ["stakeholder management", "stakeholder communication", "stakeholder engagement"],
    "Business Process Modeling": ["business process", "bpmn", "process modeling", "process improvement", "process mapping"],
    "Use Case Development": ["use case", "use cases", "user stories"],
    "Gap Analysis": ["gap analysis"],
    "UAT": ["uat", "user acceptance testing"],
    "Data Analysis": ["data analysis", "data analytics"],
    "Visio": ["visio", "ms visio", "microsoft visio"],
    "JIRA": ["jira", "jira software"],
    "Confluence": ["confluence"],
    "Trello": ["trello"],
    "Asana": ["asana"],
    "Notion": ["notion"],
    "Wireframing": ["wireframe", "wireframing", "mockup"],
    "ERP Systems": ["erp", "sap", "oracle erp", "dynamics", "netsuite"],

    # ─────────────────────────────────────────────────────────────
    # PROJECT / PROGRAM MANAGEMENT
    # ─────────────────────────────────────────────────────────────
    "Agile": ["agile", "agile methodology", "agile development"],
    "Scrum": ["scrum", "scrum master", "sprint planning", "sprint", "sprint review"],
    "Kanban": ["kanban"],
    "Waterfall": ["waterfall"],
    "PMP": ["pmp", "project management professional"],
    "Risk Management": ["risk management", "risk mitigation", "risk assessment"],
    "Budget Management": ["budget management", "cost management", "p&l", "p & l", "cost control"],
    "Vendor Management": ["vendor management", "vendor relations"],
    "Cross-functional Team Leadership": ["cross-functional team leadership", "cross-functional team", "led cross-functional team", "cross-functional collaboration", "coordinated cross-functional"],
    "Program Management": ["program management", "portfolio management"],
    "Change Management": ["change management"],
    "Resource Planning": ["resource planning", "capacity planning"],

    # ─────────────────────────────────────────────────────────────
    # SOFT SKILLS
    # ─────────────────────────────────────────────────────────────
    "Communication": ["communication skills", "verbal and written communication", "excellent communicator", "strong communication skills"],
    "Leadership": ["team leadership", "led a team", "team lead", "tech lead", "leadership skills", "executive leadership"],
    "Problem Solving": ["problem solving", "problem-solving", "analytical skills", "critical thinking"],
    "Presentation Skills": ["presentation skills", "public speaking", "presented to stakeholders"],
    "Mentoring": ["mentoring skills", "mentored team members", "coaching", "knowledge transfer"],
    "Time Management": ["time management", "deadline management", "task prioritization"],
    "Team Collaboration": ["teamwork", "team player", "team collaboration", "collaborative working"],

    # ─────────────────────────────────────────────────────────────
    # CERTIFICATIONS (treated as skills for matching)
    # ─────────────────────────────────────────────────────────────
    "CSM": ["csm", "certified scrummaster", "certified scrum master"],
    "Six Sigma": ["six sigma", "lean six sigma", "green belt", "black belt"],
    "ITIL": ["itil"],
    "CBAP": ["cbap", "certified business analysis professional"],
    "AWS Certified": ["aws certified", "aws certification", "aws solutions architect", "aws cloud practitioner"],
    "Google Cloud Certified": ["google cloud certified", "gcp certification"],
    "Azure Certified": ["azure certified", "microsoft certified", "az-900", "az-104"],
    "CompTIA": ["comptia", "comptia a+", "comptia network+", "comptia security+"],
    "CCNA": ["ccna", "cisco certified"],
    "Oracle Certified": ["ocp", "oracle certified professional"],
}


def build_alias_lookup():
    """Flatten the gazetteer into {alias_lowercase: canonical_skill} for O(1) lookup."""
    lookup = {}
    for canonical, aliases in SKILLS_GAZETTEER.items():
        lookup[canonical.lower()] = canonical
        for alias in aliases:
            lookup[alias.strip().lower()] = canonical
    return lookup


ALIAS_LOOKUP = build_alias_lookup()
ALL_CANONICAL_SKILLS = sorted(SKILLS_GAZETTEER.keys())
