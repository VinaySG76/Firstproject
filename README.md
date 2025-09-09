Firstproject/
│── app.py              # Flask main app
│── models.py           # Database models
│── requirements.txt    # Python dependencies
│── .env.sample         # Environment variables (fill in for AWS)
│── README.md
│── templates/          # HTML templates (login, register, dashboard...)
│── infra/
│    ├── terraform/     # Terraform IaC (provision EC2, S3, IAM, RDS)
│    ├── ansible/       # Ansible playbooks (configure app server)
│── Jenkinsfile         # CI/CD pipeline
