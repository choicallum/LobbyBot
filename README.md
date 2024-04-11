<a name="readme-top"></a>
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]
[![LinkedIn][linkedin-shield]][linkedin-url]


<h3 align="center">LobbyBot</h3>

  <p align="center">
    A lightweight and easy-to-use discord bot to plan gaming or social events!
    <br />
    <a href="https://github.com/choicallum/LobbyBot/issues">Report Bug</a>
    ·
    <a href="https://github.com/choicallum/LobbyBot/issues">Request Feature</a>
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project

LobbyBot is a lightweight discord bot allowing users to plan lobbies for gaming or social events on discord. 

It is NOT publically hosted as of now, but can easily be setup on a free trial of an EC2 AWS instance, or any other cloud setup (or even locally!).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- GETTING STARTED -->
### Prerequisites
* Python 3.8 or higher [Download](https://www.python.org/downloads/)
* discord.py

  For Windows:
  ```sh
  py -3 -m pip install -U discord.py
  ```
  For Linux/Mac
  ```sh
  python3 -m pip install -U discord.py
  ```
* python-dotenv
  ```sh
  pip install python-dotenv
  ```

### Installation

1. Get a free API Key at [https://discord.com/developers/applications](https://discord.com/developers/applications) by creating a new application.
2. On the same application, go to OAuth2>URL Generator. Check the "bot" scope, and give it at least the following permissions:
   * Send Messages
   * Add Reactions
   * Use Slash Commands
   * Manage Messages
  
    Then, add the bot to your server.
3. Clone the repo
   ```sh
   git clone https://github.com/choicallum/LobbyBot.git
   ```
4. Enter your API in `.env.example`
   ```py
   DISCORD_API_TOKEN = 'ENTER YOUR API KEY'
   ```
5. Create and enter the paths for the Users and Logs folders.
   ```py
   USERS_PATH = '/LobbyBot/users'
   LOG_PATH = '/LobbyBot/logs'
   ```
6. Rename `.env.example` to `.env`
7. Run main.py!

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- ROADMAP -->
## Roadmap

- [ ] Add game integration (i.e. can create certain rank thresholds for lobbies that are checked when you sign up)
- [ ] Make it so lobbys actually expire after the time finishes

See the [open issues](https://github.com/choicallum/LobbyBot/issues) for a  list of proposed features (and known issues).

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- LICENSE -->
## License

Distributed under the MIT License. See `LICENSE.txt` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTACT -->
## Contact

[@CallumChoi](https://twitter.com/callumchoi?lang=en) - choicallum@gmail.com

[https://github.com/choicallum/LobbyBot](https://github.com/choicallum/LobbyBot)

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/choicallum/LobbyBot.svg?style=for-the-badge
[contributors-url]: https://github.com/choicallum/LobbyBot/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/choicallum/LobbyBot.svg?style=for-the-badge
[forks-url]: https://github.com/choicallum/LobbyBot/network/members
[stars-shield]: https://img.shields.io/github/stars/choicallum/LobbyBot.svg?style=for-the-badge
[stars-url]: https://github.com/choicallum/LobbyBot/stargazers
[issues-shield]: https://img.shields.io/github/issues/choicallum/LobbyBot.svg?style=for-the-badge
[issues-url]: https://github.com/choicallum/LobbyBot/issues
[license-shield]: https://img.shields.io/github/license/choicallum/LobbyBot.svg?style=for-the-badge
[license-url]: https://github.com/choicallum/LobbyBot/blob/master/LICENSE.txt
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=for-the-badge&logo=linkedin&colorB=555
[linkedin-url]: https://linkedin.com/in/choicallum
