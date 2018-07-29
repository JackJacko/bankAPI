from flask import Flask, jsonify, request
from flask_restful import Api, Resource
from pymongo import MongoClient
from bson.json_util import dumps
import bcrypt
import json
import time
import datetime

app = Flask(__name__)
api = Api(app)

client = MongoClient("mongodb://db:27017")
db = client.bankDB
bankUsers = db["Users"]

transactionCost = int(99) #cents
interestRate = 0.1

def verify_pw(usr, pwd):
    h_pwd = bankUsers.find({"Username":usr})[0]["Password"]

    if bcrypt.hashpw(pwd.encode('utf8'), h_pwd) == h_pwd:
        return True
    else:
        return False

def check_username(usr):
    if bankUsers.find({"Username":usr},{"Username":1}).count() > 0:
        return True
    else:
        return False

def generate_retJson(status, message):
    retJson = {
        "Message": message,
        "Status code": status
    }
    return jsonify(retJson)

def check_funds(usr):
    funds = bankUsers.find({"Username":usr})[0]["Funds"]
    return funds

def check_debt(usr):
    debt = bankUsers.find({"Username":usr})[0]["Debt"]
    return debt

def log_operation(usr,type,amount):
    currentUser = db[usr]
    currentUser.insert_one({
        "Username": usr,
        "Date & Time": datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S'),
        "Operation": type,
        "Amount": amount/100
    })

def update_funds(usr,prev_amt,add_amt,type):
    bankUsers.update_one({
        "Username":usr
    }, {
        "$set": {
            "Funds": prev_amt + add_amt
        }
    })
    log_operation(usr,type,add_amt)

def update_debt(usr,prev_dbt,add_dbt):
    bankUsers.update_one({
        "Username":usr
    }, {
        "$set": {
            "Debt": prev_dbt + add_dbt
        }
    })

class Register(Resource):
    def post(self):
        # get posted data
        Data = request.get_json()
        # check data for missing input
        if 'Username' not in Data or 'Password' not in Data:
            return generate_retJson(301,"An error happened: Input data is missing.")
        # assign data to variables
        usr = Data['Username']
        pwd = Data['Password']
        # check if username is in use
        if check_username(usr):
            return generate_retJson(302,"An error happened: Username is already taken.")
        # hash the password
        h_pwd = bcrypt.hashpw(pwd.encode('utf8'), bcrypt.gensalt())
        # store username and hashed password
        bankUsers.insert_one({
            "Username": usr,
            "Password": h_pwd,
            "Funds": int(0),
            "Debt": int(0)
        })
        # store first operation
        log_operation(usr,"Init",0)
        # confirm successful registration
        return generate_retJson(200,"Your registration was successful.")

class Deposit(Resource):
    def post(self):
        # get posted data
        Data = request.get_json()
        # check data for missing input
        if 'Username' not in Data or 'Password' not in Data or 'DepoAmount' not in Data:
            return generate_retJson(301,"An error happened: Input data is missing.")
        # assign data to variables
        usr = Data['Username']
        pwd = Data['Password']
        dep_amt = int(Data['DepoAmount']*100) # cents
        # check if account exists
        if not check_username(usr):
            return generate_retJson(302,"An error happened: Username not in database. Please check spelling.")
        # check if password is correct
        if not verify_pw("admin", pwd):
            return generate_retJson(303,"An error happened: Password is incorrect. Admin access only.")
        # check if DepoAmount is valid
        if dep_amt <= 0:
            return generate_retJson(304,"An error happened: Invalid deposit amount.")
        # update funds and return success
        c_amt = check_funds(usr)
        update_funds(usr,c_amt,dep_amt,"Deposit")
        return generate_retJson(200,"Your deposit was accepted.")

class Withdraw(Resource):
    def post(self):
        # get posted data
        Data = request.get_json()
        # check data for missing input
        if 'Username' not in Data or 'Password' not in Data or 'WithdrawAmount' not in Data:
            return generate_retJson(301,"An error happened: Input data is missing.")
        # assign data to variables
        usr = Data['Username']
        pwd = Data['Password']
        wtdw_amt = int(Data['WithdrawAmount']*100) #cents
        op_amt = wtdw_amt+transactionCost
        # check if account exists
        if not check_username(usr):
            return generate_retJson(302,"An error happened: Username not in database. Please check spelling or register.")
        # check if password is correct
        if not verify_pw(usr, pwd):
            return generate_retJson(303,"An error happened: Password is incorrect.")
        # check if WithdrawAmount is valid
        if wtdw_amt <= 0:
            return generate_retJson(304,"An error happened: Invalid withdraw amount.")
        # check if user has sufficient funds for withdrawal
        if check_funds(usr) < wtdw_amt:
            return generate_retJson(305,"An error happened: Insufficient funds. Check your account balance.")
        # update funds and return success
        c_amt = check_funds(usr)
        ad_amt = check_funds("admin")
        update_funds(usr,c_amt,-op_amt,"Withdrawal")
        update_funds("admin",ad_amt,transactionCost,"TransFee")
        ### give_cash(wtdw_amt) this should communicate with an ATM device ###
        return generate_retJson(200,"Your withdrawal was successful.")

class Transfer(Resource):
    def post(self):
        # get posted data
        Data = request.get_json()
        # check data for missing input
        if 'Username' not in Data or 'Password' not in Data or 'TargetUser' not in Data or 'TransfAmount' not in Data:
            return generate_retJson(301,"An error happened: Input data is missing.")
        # assign data to variables
        usr = Data['Username']
        pwd = Data['Password']
        tgt_usr = Data['TargetUser']
        tsf_amt = int(Data['TransfAmount']*100) #cents
        op_amt = tsf_amt+transactionCost
        # check if account exists
        if not check_username(usr):
            return generate_retJson(302,"An error happened: Username not in database. Please check spelling or register.")
        # check if password is correct
        if not verify_pw(usr, pwd):
            return generate_retJson(303,"An error happened: Password is incorrect.")
        # check if TransfAmount is valid
        if tsf_amt <= 0:
            return generate_retJson(304,"An error happened: Invalid transfer amount.")
        # check if user has sufficient funds for transfer
        if check_funds(usr) < op_amt:
            return generate_retJson(305,"An error happened: Insufficient funds. Check your account balance.")
        # transfer funds and return success
        c_amt = check_funds(usr)
        ad_amt = check_funds("admin")
        tgt_amt = check_funds(tgt_usr)
        update_funds(usr,c_amt,-op_amt,"Transfer")
        update_funds("admin",ad_amt,transactionCost,"TransFee")
        update_funds(tgt_usr,tgt_amt,tsf_amt,"Transfer")
        return generate_retJson(200,"Your transfer was successful.")

class CheckBalance(Resource):
    def post(self):
        # get posted data
        Data = request.get_json()
        # check data for missing input
        if 'Username' not in Data or 'Password' not in Data:
            return generate_retJson(301,"An error happened: Input data is missing.")
        # assign data to variables
        usr = Data['Username']
        pwd = Data['Password']
        # check if account exists
        if not check_username(usr):
            return generate_retJson(302,"An error happened: Username not in database. Please check spelling or register.")
        # check if password is correct
        if not verify_pw(usr, pwd):
            return generate_retJson(303,"An error happened: Password is incorrect.")
        # return balance and report success
        retJson = {}
        retJson["Message"] = "Your current balance is:"
        retJson["Funds"] = check_funds(usr)/100
        retJson["Debt"] = check_debt(usr)/100
        retJson["Status code"] = 200
        return retJson

class IssueLoan(Resource):
    def post(self):
        # get posted data
        Data = request.get_json()
        # check data for missing input
        if 'Username' not in Data or 'Password' not in Data or 'LoanAmount' not in Data:
            return generate_retJson(301,"An error happened: Input data is missing.")
        # assign data to variables
        usr = Data['Username']
        pwd = Data['Password']
        loan_amt = int(Data['LoanAmount']*100) #cents
        # check if account exists
        if not check_username(usr):
            return generate_retJson(302,"An error happened: Username not in database. Please check spelling.")
        # check if password is correct
        if not verify_pw("admin", pwd):
            return generate_retJson(303,"An error happened: Password is incorrect. Admin access only.")
        # check if LoanAmount is valid
        if loan_amt <= 0:
            return generate_retJson(304,"An error happened: Invalid loan amount.")
        # update funds and debt and return success
        c_amt = check_funds(usr)
        ad_amt = check_funds("admin")
        c_dbt = check_debt(usr)
        update_funds(usr,c_amt,loan_amt,"LoanIssue")
        update_funds("admin",ad_amt,-loan_amt,"LoanIssue")
        update_debt(usr,c_dbt,loan_amt+int(loan_amt*interestRate))
        return generate_retJson(200,"Your loan was issued.")

class PayLoan(Resource):
    def post(self):
        # get posted data
        Data = request.get_json()
        # check data for missing input
        if 'Username' not in Data or 'Password' not in Data or 'PayAmount' not in Data:
            return generate_retJson(301,"An error happened: Input data is missing.")
        # assign data to variables
        usr = Data['Username']
        pwd = Data['Password']
        pay_amt = int(Data['PayAmount']*100) #cents
        # check if account exists
        if not check_username(usr):
            return generate_retJson(302,"An error happened: Username not in database. Please check spelling or register.")
        # check if password is correct
        if not verify_pw(usr, pwd):
            return generate_retJson(303,"An error happened: Password is incorrect.")
        # check if PayAmount is valid
        if pay_amt <= 0:
            return generate_retJson(304,"An error happened: Invalid loan amount.")
        # check if user has sufficient funds for transfer
        if check_funds(usr) < pay_amt:
            return generate_retJson(305,"An error happened: Insufficient funds. Check your account balance.")
        # check if user is paying too much and in that case pay only correct amount and return warning and success
        # else update funds and debt normally and return success
        c_amt = check_funds(usr)
        ad_amt = check_funds("admin")
        c_dbt = check_debt(usr)
        if c_dbt < pay_amt:
            pay_amt = c_dbt
            update_funds(usr,c_amt,-pay_amt,"LoanPayment")
            update_funds("admin",ad_amt,pay_amt,"LoanPayment")
            update_debt(usr,c_dbt,-pay_amt)
            return generate_retJson(200,"Payment amount was eccessive; only correct amount was taken. Your payment was successful.")
        else:
            update_funds(usr,c_amt,-pay_amt,"LoanPayment")
            update_funds("admin",ad_amt,pay_amt,"LoanPayment")
            update_debt(usr,c_dbt,-pay_amt)
            return generate_retJson(200,"Your payment was successful.")

class Delete(Resource):
    def post(self):
        # get posted data
        Data = request.get_json()
        # check data for missing input
        if 'Username' not in Data or 'Password' not in Data:
            return generate_retJson(301,"An error happened: Input data is missing.")
        # assign data to variables
        usr = Data['Username']
        pwd = Data['Password']
        # check if account exists
        if not check_username(usr):
            return generate_retJson(302,"An error happened: Username not in database. Please check spelling.")
        # check if password is correct
        if not verify_pw("admin", pwd):
            return generate_retJson(303,"An error happened: Password is incorrect. Admin access only.")
        # delete account and return success
        bankUsers.delete_one({"Username": usr})
        return generate_retJson(200,"The account was deleted successfully.")

class Movements(Resource):
    def post(self):
        # get posted data
        Data = request.get_json()
        # check data for missing input
        if 'Username' not in Data or 'Password' not in Data:
            return generate_retJson(301,"An error happened: Input data is missing.")
        # assign data to variables
        usr = Data['Username']
        pwd = Data['Password']
        # check if account exists
        if not check_username(usr):
            return generate_retJson(302,"An error happened: Username not in database. Please check spelling.")
        # check if password is correct
        if not verify_pw(usr, pwd):
            return generate_retJson(303,"An error happened: Password is incorrect.")
        # recover and return operation logs
        currentUser = db[usr]
        retJson = currentUser.find({"Username":usr},{"_id":0})
        dumpd = dumps(retJson)
        return dumpd

api.add_resource(Register, "/signup")
api.add_resource(Deposit, "/deposit")
api.add_resource(Withdraw, "/withdraw")
api.add_resource(Transfer, "/transfer")
api.add_resource(CheckBalance, "/balance")
api.add_resource(IssueLoan, "/issueLoan")
api.add_resource(PayLoan, "/payLoan")
api.add_resource(Delete, "/delete")
api.add_resource(Movements, "/movements")

if __name__=="__main__":
    app.run(host ='0.0.0.0', debug = True)
