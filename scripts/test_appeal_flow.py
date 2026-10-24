import json
import urllib.request
import http.cookiejar

def run_test():
    # 1. Student logs in and creates an appeal
    cj_s = http.cookiejar.CookieJar()
    op_s = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj_s))
    csrf_s = json.loads(op_s.open('http://127.0.0.1:5000/api/v1/auth/csrf').read())['data']['csrf_token']
    login_data = json.dumps({'email': 'aarthi@elite.edu', 'password': 'Elite@1234', 'portal': 'student'}).encode('utf-8')
    req = urllib.request.Request('http://127.0.0.1:5000/api/v1/auth/login', data=login_data, headers={'Content-Type': 'application/json', 'X-CSRF-Token': csrf_s})
    op_s.open(req)

    appeal_data = json.dumps({'reason': 'Please review my score for the DSA Day 1 assessment.', 'attempt_id': 1}).encode('utf-8')
    req = urllib.request.Request('http://127.0.0.1:5000/api/v1/student/appeals', data=appeal_data, headers={'Content-Type': 'application/json', 'X-CSRF-Token': csrf_s})
    res = op_s.open(req)
    created = json.loads(res.read())['data']
    appeal_id = created['id']
    print(f'Created appeal ID: {appeal_id}')

    # 2. Faculty logs in and assigns appeal to themselves
    cj_f = http.cookiejar.CookieJar()
    op_f = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj_f))
    csrf_f = json.loads(op_f.open('http://127.0.0.1:5000/api/v1/auth/csrf').read())['data']['csrf_token']
    login_data = json.dumps({'email': 'faculty@elite.edu', 'password': 'Elite@1234', 'portal': 'faculty'}).encode('utf-8')
    req = urllib.request.Request('http://127.0.0.1:5000/api/v1/auth/login', data=login_data, headers={'Content-Type': 'application/json', 'X-CSRF-Token': csrf_f})
    op_f.open(req)

    req = urllib.request.Request(f'http://127.0.0.1:5000/api/v1/faculty/appeals/{appeal_id}/assign', data=b'{}', headers={'Content-Type': 'application/json', 'X-CSRF-Token': csrf_f})
    assigned = json.loads(op_f.open(req).read())['data']
    print('Faculty assigned appeal:', assigned['status'], 'Reviewer:', assigned['assigned_reviewer'], 'Instruction:', assigned['instruction_message'])

    # 3. Student fetches appeals & dashboard
    res = op_s.open('http://127.0.0.1:5000/api/v1/student/appeals')
    st_appeals = json.loads(res.read())['data']
    print('Student appeals received:', [(a['id'], a['status'], a['instruction_message']) for a in st_appeals])

    res = op_s.open('http://127.0.0.1:5000/api/v1/student/dashboard')
    st_dash = json.loads(res.read())['data']
    print('Student dashboard faculty instructions:', st_dash.get('faculty_instructions'))

if __name__ == '__main__':
    run_test()
