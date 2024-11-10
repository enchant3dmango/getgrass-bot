# :seedling: GetGrass Bot

## Eligibility Checker & Claimer
- [Eligibility Checker](https://grassfoundation.io/eligibility)
- [Claimer](https://github.com/MsLolita/Grass-Claimer)

## How to Run?
- Run `apt install python3-pip`.
- Go to `GetGrass-Bot` dir.
- Run `pip3 install -r requirements.txt`.
- Create `id.txt` file and put your user ID there.
- Create `proxy.txt` file and put your proxy in newline text there. Example:
    ```txt
    http://auth-1@host:port
    http://auth-2@host:port
    http://auth-3@host:port
    http://auth-n@host:port
- Run `screen -S grass`. Choose one of the below steps depending on your condition:
    - Run `python3 main.py`.
    - Run `proxyless.py` if not using any proxy.
- Ctrl + A, then D to detach the screen, it will run in the background.

## Warnings!
- :warning: Just update the `proxy.txt` when you wanna add or change the proxy list, no need to restart the service!
- :warning: Don't touch the `id.txt` when the service is running!

## Referral
https://app.getgrass.io/register/?referralCode=SxjVUVv2xt1LNCp

## How to Get the user_id?
1. Open the link to log in https://app.getgrass.io/dashboard.
2. Press F12 on the page to open the console and enter the code `localStorage.getItem('userId')` or click application, check Local Storage, and copy the userId value.

LFG! :rocket:
