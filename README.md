# RegretBlocker Data Collection Tool
Users' decisions in recommendation systems are prone to be similar in similar decision frames. Even after watching a video, a socially engineered interface may make them signal their like of content that they do not like. RegretBlocker deletes content that users state they regret **outside of a platform**. This data collection tool can be run and deployed on any server capable of running docker. We provide installation instructions and our data collection tool. We provide learning tools for your personal RegretBlocker in the future.

## Table of Contents
2. [Installation](#installation)
3. [Usage](#usage)
4. [Project Structure](#project-structure)
5. [Contact](#contact)

## Installation
1. Clone the repository: `git clone https://github.com/Algorithmic-Personalization/Regret-Blocker.git`
2. Navigate to the project directory: `cd Regret-Blocker`
3. [Install Docker Compose](https://docs.docker.com/compose/install/)
4. Install dependencies: `pip install -r requirements.txt`
5. Fill

## Usage
To start the application, run:
```bash
docker-compose up -d # start the docker image in the background
docker-compose exec flask db init # Initialize a new database schema
docker-compose exec flask db migrate -m "Initial migration" # Apply the migration to the database
flask db upgrade
docker-compose restart
```
Then, the application should be accessible under http://127.0.0.1:5001/upload?uid=user_id for any `user_id`.

## Project Structure
`app/` contains the main application logic.
- `migrations/`: Database migration files.
- `static/`: contains `css` and `js` files
- `templates/`: contains `html` templates
- `uploads/`: stores uploaded data for regrets

- `services/`: Business logic.
- `utils/`: Utility functions.
- `templates/`: HTML templates.

- `scripts/`: Utility scripts.

## Contact
For questions or support, contact [recsysexp@mit.edu](mailto:recsysexp@mit.edu).
