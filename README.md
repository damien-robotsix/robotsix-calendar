# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/damien-robotsix/robotsix-calendar-agent/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                          |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|-------------------------------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| src/robotsix\_calendar\_agent/\_\_init\_\_.py                 |        6 |        0 |        0 |        0 |    100% |           |
| src/robotsix\_calendar\_agent/agent/\_\_init\_\_.py           |      126 |        0 |       34 |        1 |     99% | 341-\>343 |
| src/robotsix\_calendar\_agent/caldav\_client/\_\_init\_\_.py  |       97 |       11 |       34 |        1 |     91% |194-195, 205-208, 238-244 |
| src/robotsix\_calendar\_agent/caldav\_client/\_shared.py      |       94 |        1 |        8 |        1 |     98% |       145 |
| src/robotsix\_calendar\_agent/caldav\_client/calendar\_ops.py |       86 |        2 |       20 |        2 |     96% |  201, 238 |
| src/robotsix\_calendar\_agent/caldav\_client/contact\_ops.py  |      102 |       11 |       32 |        4 |     89% |46, 68-70, 76-78, 85-88 |
| src/robotsix\_calendar\_agent/caldav\_client/exceptions.py    |       19 |        0 |        0 |        0 |    100% |           |
| src/robotsix\_calendar\_agent/caldav\_client/task\_ops.py     |       18 |        0 |        2 |        0 |    100% |           |
| src/robotsix\_calendar\_agent/entrypoint/\_\_init\_\_.py      |       25 |        0 |        0 |        0 |    100% |           |
| src/robotsix\_calendar\_agent/entrypoint/\_\_main\_\_.py      |        4 |        4 |        2 |        0 |      0% |       3-8 |
| src/robotsix\_calendar\_agent/healthcheck/\_\_init\_\_.py     |       43 |        1 |        6 |        1 |     96% |        99 |
| src/robotsix\_calendar\_agent/intent\_parser/\_\_init\_\_.py  |       60 |        0 |        2 |        0 |    100% |           |
| src/robotsix\_calendar\_agent/settings/\_\_init\_\_.py        |       26 |        0 |        2 |        0 |    100% |           |
| **TOTAL**                                                     |  **706** |   **30** |  **142** |   **10** | **95%** |           |


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/damien-robotsix/robotsix-calendar-agent/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/damien-robotsix/robotsix-calendar-agent/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/damien-robotsix/robotsix-calendar-agent/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/damien-robotsix/robotsix-calendar-agent/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2Fdamien-robotsix%2Frobotsix-calendar-agent%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/damien-robotsix/robotsix-calendar-agent/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.