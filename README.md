# CI/CD for Trajectory-based Molecular: From Trajectories to Training Data
This repository contains the code for automating the process of data generation from molecular trajectories using continuous integration and deployment (CI/CD) tools.

## Description
The extraction of useful information from a molecular trajectory has always been a labor-intensive manual procedure. The purpose of this project is to use cutting-edge CI/CD for data science tools to fully automate this procedure. The project was built on top of many frameworks and technologies, including GIT+DVC, Celery, Redis, and Webhooks.

A webhook is set up to trigger whenever a push is made to a Gitea repository (it can be any git repository). This launches a fresh instance of Celery, configured to use a local Redis server as its broker and backend. While the backend is used to store completed tasks, the broker acts as a message queue for assigning tasks to worker processes.
## Setup and Installation
### Prerequisites
- Python
- Redis Server
- Celery
- GIT
- DVC
- Sentry SDK
- LocalTunnel
- Webhooks

### Installation
1. Clone the repository


```
git clone <repository_url>

```
2. Install required Python packages
```
pip install -r requirements.txt

```
3. Set up your Redis server, Celery and other tools
## Usage
## Contributing
## License
## Contact
- <a href="mailto:YourEmail@example.com" target="_new"></a>
## Acknowledgments
Include any acknowledgments here.
<hr>



***