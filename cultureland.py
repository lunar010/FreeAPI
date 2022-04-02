from textwrap import indent
import requests, re
from mTransKey.transkey import mTransKey
from flask import Flask,jsonify, request
import hashlib, random, json

class Cultureland:
    def __init__(self, id_, pw):
        self.s = requests.session()
        self.id_ = id_
        self.pw = pw

    def _islogin(self):
        resp = self.s.post("https://m.cultureland.co.kr/mmb/isLogin.json")
        if resp.text != 'true':
            return False
        else:
            return True

    def _login(self):
        if self._islogin():
            return True
        mtk = mTransKey(self.s, "https://m.cultureland.co.kr/transkeyServlet")
        pw_pad = mtk.new_keypad("qwerty", "passwd", "passwd")
        encrypted = pw_pad.encrypt_password(self.pw)
        hm = mtk.hmac_digest(encrypted.encode())
        self.s.post("https://m.cultureland.co.kr/mmb/loginProcess.do", data={"agentUrl": "", "returnUrl": "", "keepLoginInfo": "", "phoneForiOS": "", "hidWebType": "other", "userId": self.id_, "passwd": "*" * len(self.pw), "transkeyUuid": mtk.get_uuid(), "transkey_passwd": encrypted, "transkey_HM_passwd": hm})
        if self._islogin():
            return True
        else:
            return False

    def get_balance(self):
        if not self._login():
            return False,
        resp = self.s.post("https://m.cultureland.co.kr/tgl/getBalance.json")
        result = resp.json()
        if result['resultCode'] != "0000":
            return False, result
        return True,int(result['blnAmt']),int(result['bnkAmt']),int(result['remainCash']),int(result['limitCash']),result['memberKind'] # (True, 사용가능, 보관중, 남은한도, 총한도, 상태)

    def charge(self, pin):
        if not self._login():
            return False,
        pin = re.sub(r'[^0-9]', '', pin)
        if len(pin) != 16 and len(pin) != 18:
            return 3,"상품권 길이 불일치"
        pin = [pin[i:i + 4] if i != 12 and len(pin) > 12 else pin[i:] for i in range(0, 14, 4)]
        self.s.cookies.set("appInfoConfig", '"cookieClientType=IPHONE&cookieKeepLoginYN=F"')
        self.s.get('https://m.cultureland.co.kr/csh/cshGiftCard.do')
        resp = self.s.post("https://m.cultureland.co.kr/csh/cshGiftCardProcess.do", data={'scr11': pin[0], 'scr12': pin[1], 'scr13': pin[2], 'scr14': pin[-1]})
        self.s.cookies.set("appInfoConfig", '"cookieClientType=MWEB&cookieKeepLoginYN=F"')
        #print(resp.text)
        result = resp.text.split('<td><b>')[1].split("</b></td>")[0]
        if '충전 완료' in resp.text:
            return 1, int(resp.text.split("<dd>")[1].split("원")[0].replace(",", ""))
        elif result in ['이미 등록된 문화상품권', '상품권 번호 불일치', '판매 취소된 문화상품권']:
            return 0,result
        elif '등록제한(10번 등록실패)' in result:
            return 2,"등록제한"
        else:
            return 3,result

    def gift(self, amount, phone=None):
        if not self._login():
            return "sFalse",
        resp = self.s.post('https://m.cultureland.co.kr/tgl/flagSecCash.json').json()
        #print(str(resp))
        user_key = resp['userKey']
        if not phone:
            phone = resp['Phone']
        self.s.get('https://m.cultureland.co.kr/gft/gftPhoneApp.do')
        resp = self.s.post('https://m.cultureland.co.kr/gft/gftPhoneCashProc.do', data={"revEmail": "", "sendType": "S", "userKey": user_key, "limitGiftBank": "N", "giftCategory": "O", "amount": str(amount), "quantity": "1", "revPhone": str(phone), "sendTitl": "", "paymentType": "cash"})
        #print(resp.text)
        if '요청하신 정보로 전송' in resp.text:
            return True,
        else:
            print(resp.text)
            return False,resp.text

app = Flask(__name__)

def true_jsonconvert(id,stat,normal,safe, current_hando,hando):
    return '''<pre>{
    "잔액 조회": {
        "id": {
            "결과 메시지": "조회 성공",
            "계정 상태": "accountstatus",
            "컬쳐캐쉬": {
                "사용 가능 컬쳐캐쉬": normal,
                "안심금고": safe,
                "총 컬쳐캐쉬": plus
            },
            "한도":{
                "남은 컬쳐캐쉬 한도": current_hando,
                "총 컬쳐캐쉬 한도": hando
            }
        }
    }
}</pre>'''.replace("accountstatus",stat).replace("id", id).replace("normal",str(normal)).replace("safe",str(safe)).replace("plus",str(safe+normal)).replace("current_hando", str(current_hando)).replace("hando", str(hando))

def false_jsonconvert(id):
    return '''<pre>{
    "잔액 조회": {
        "id": {
            "결과 메시지": "로그인 실패",
            "계정 상태": "조회 불가",
            "컬쳐캐쉬": {
                "사용 가능 컬쳐캐쉬": "조회불가",
                "안심금고": "조회불가",
                "총 컬쳐캐쉬": "조회불가"
            },
            "한도":{
                "남은 컬쳐캐쉬 한도": "조회불가",
                "총 컬쳐캐쉬 한도": "조회불가"
            }
        }
    }
}</pre>'''.replace("id", id)

def pin_true_jsonconvert(id, money, pin):
    return '''<pre>{
    "상품권 충전": {
        "id" {
            "상품권 핀": pin,
            "결과 메시지": "상품권 충전 성공",
            "금액": money
        }
    }
}</pre>'''.replace("id", id).replace("pin", pin).replace("money", str(money))

def pin_false_jsonconvert(id, fail, pin):
    return '''<pre>{
    "상품권 충전": {
        "id" {
            "상품권 핀": pin,
            "결과 메시지": "msg"
        }
    }
}</pre>'''.replace("id", id).replace("pin", pin).replace("msg", str(fail).replace("'", ""))

def v2pin_false_jsonconvert(id, pin):
    return '''<pre>{
    "상품권 충전": {
        "id" {
            "상품권 핀": pin,
            "결과 메시지": "상품권 등록 제한"
        }
    }
}</pre>'''.replace("id", id).replace("pin", pin)

def v3pin_false_jsonconvert(id, pin, data):
    return '''<pre>{
    "상품권 충전": {
        "id" {
            "상품권 핀": pin,
            "결과 메시지": "data"
        }
    }
}</pre>'''.replace("id", id).replace("pin", pin).replace("data", data)

def v5false_jsonconvert(id, pin):
    return '''<pre>{
    "상품권 충전": {
        "id" {
            "상품권 핀": pin,
            "결과 메시지": "로그인 실패"
        }
    }
}</pre>'''.replace("id", id).replace("pin", pin)

def true_with_jsonconvert(id, phone):
    return '''<pre>{
    "상품권 출금": {
        "id" {
            "전화번호": phone,
            "결과 메시지": "출금 성공"
        }
    }
}</pre>'''.replace("id", id).replace("phone", phone)

def false_with_jsonconvert(id, phone):
    return '''<pre>{
    "상품권 출금": {
        "id" {
            "전화번호": phone,
            "결과 메시지": "출금 실패"
        }
    }
}</pre>'''.replace("id", id).replace("phone", phone)

def v2false_with_jsonconvert(id, phone):
    return '''<pre>{
    "상품권 출금": {
        "id" {
            "전화번호": phone,
            "결과 메시지": "로그인 실패"
        }
    }
}</pre>'''.replace("id", id).replace("phone", phone)

def v3false_with_jsonconvert(id, phone):
    return '''<pre>{
    "상품권 출금": {
        "id" {
            "전화번호": phone,
            "결과 메시지": "전화번호 길이 불일치"
        }
    }
}</pre>'''.replace("id", id).replace("phone", phone)

@app.route("/api/withdraw")
def withdraw():
    global status
    id = request.args.get('id')
    passw = request.args.get('password')
    amount = int(request.args.get('amount'))
    phone = request.args.get('phone')
    status = 0
    if status == 0:
        if len(str(phone).replace("-", "")) == 11:
            cl = Cultureland(id, passw)
            data = str(cl.gift(amount, phone)).split(",")
            if not "sFalse" in data[0]:
                if str(data[0]) == "True":
                    string = true_with_jsonconvert(id=id,phone=phone)
                    return str(string)
                else:
                    string = false_with_jsonconvert(id=id,phone=phone)
                    return str(string)
            else:
                string = v2false_with_jsonconvert(id=id,phone=phone)
                return str(string)
        else:
            string = v3false_with_jsonconvert(id=id,phone=phone)
            return str(string)

@app.route("/api/charge")
def pincode():
    global status
    id = str(request.args.get('id'))
    passw = str(request.args.get('password'))
    pincode = str(request.args.get('pin'))
    status = 0
    if status == 0:
        cl = Cultureland(id, passw)
        data = str(cl.charge(pincode)).replace("(", "").replace(")", "").split(",")
        if str(data[0]) == "False":
            string = v5false_jsonconvert(id=id, pin=pincode)
            return str(string)
        else:
            if int(data[0]) == 1:
                string = pin_true_jsonconvert(id=id,money=int(data[1]), pin=pincode)
                return str(string)
            elif int(data[0]) == 0:
                if "이미 등록된 문화상품권" in data[1]:
                    data[1] = data[1].replace("'이미 등록된 문화상품권'", "1").replace(" ","").replace("1", "이미 등록된 문화상품권")
                elif "상품권 번호 불일치" in data[1]:
                    data[1] = data[1].replace("'상품권 번호 불일치'", "1").replace(" ","").replace("1", "상품권 번호 불일치")
                else:
                    data[1] = data[1].replace("''판매 취소된 문화상품권'", "1").replace(" ","").replace("1", "판매 취소된 문화상품권")
                string = pin_false_jsonconvert(id=id,fail=data[1], pin=pincode)
                return str(string)
            elif int(data[0]) == 2:
                string = v2pin_false_jsonconvert(id=id, pin=pincode)
                return str(string)
            elif int(data[0]) == 3:
                if "상품권 길이 불일치" in data[1]:
                    data[1] = data[1].replace("'상품권 길이 불일치'", "1").replace(" ","").replace("1", "상품권 길이 불일치")
                string = v3pin_false_jsonconvert(id=id, pin=pincode, data=data[1])
                return str(string)
            else:
                return "API 에러"
@app.route("/api/balance")
def main():
    global status
    id = request.args.get('id')
    passw = request.args.get('password')
    status = 0
    if status == 0:
        cl = Cultureland(id, passw)
        if "True" in str(cl.get_balance()):
            bd = str(cl.get_balance()).replace("(", "").replace(")", "").replace(" ", "").split(",")
            if bd[5].replace("'", "") == "M":
                dat = "휴대폰 인증"
            elif bd[5].replace("'", "") == "H":
                dat = "휴대폰 본인인증"
            else:
                dat = "이메일 인증"
            string = true_jsonconvert(id=id,stat=dat,normal = int(bd[1]), safe = int(bd[2]), current_hando=bd[3],hando=bd[4])
            return str(string)
        elif "False" in str(cl.get_balance()):
            string = false_jsonconvert(id=id)
            return str(string)
        else:
            return "API 에러"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
