"""Audit StockFlow in installed Chromium, using an isolated disposable database.

No browser driver or additional Python dependency is required. The Chrome DevTools
Protocol transport below implements only the WebSocket operations this audit uses.
Run from the repository: .venv/Scripts/python.exe scripts/ui_qa.py --help
"""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timedelta
import hashlib
from html.parser import HTMLParser
import json
import logging
import os
from pathlib import Path
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class CDP:
    def __init__(self, url):
        parsed = urlsplit(url)
        self.sock = socket.create_connection((parsed.hostname, parsed.port), timeout=30)
        key = base64.b64encode(secrets.token_bytes(16)).decode()
        request = (f"GET {parsed.path} HTTP/1.1\r\nHost: {parsed.netloc}\r\n"
                   f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
                   f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(request.encode())
        response = b""
        while not response.endswith(b"\r\n\r\n"):
            response += self._read(1)
        expected = base64.b64encode(hashlib.sha1(
            (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
        if b" 101 " not in response or expected not in response:
            raise RuntimeError(f"WebSocket handshake failed: {response[:200]!r}")
        self.sequence = 0
        self.exceptions = []

    def _read(self, length):
        data = b""
        while len(data) < length:
            chunk = self.sock.recv(length - len(data))
            if not chunk:
                raise RuntimeError("Chromium closed the DevTools connection")
            data += chunk
        return data

    def _send(self, data, opcode=1):
        mask = secrets.token_bytes(4)
        length = len(data)
        header = bytes([0x80 | opcode])
        if length < 126:
            header += bytes([0x80 | length])
        elif length < 65536:
            header += bytes([0x80 | 126]) + struct.pack("!H", length)
        else:
            header += bytes([0x80 | 127]) + struct.pack("!Q", length)
        self.sock.sendall(header + mask + bytes(c ^ mask[i % 4] for i, c in enumerate(data)))

    def _receive(self):
        message = b""
        while True:
            first, second = self._read(2)
            length = second & 127
            if length == 126:
                length = struct.unpack("!H", self._read(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read(8))[0]
            mask = self._read(4) if second & 128 else None
            data = self._read(length)
            if mask:
                data = bytes(c ^ mask[i % 4] for i, c in enumerate(data))
            opcode = first & 15
            if opcode == 8:
                raise RuntimeError("Chromium closed the WebSocket")
            if opcode == 9:
                self._send(data, 10)
                continue
            if opcode in (0, 1):
                message += data
                if first & 128:
                    return json.loads(message)

    def call(self, method, **params):
        self.sequence += 1
        identifier = self.sequence
        self._send(json.dumps({"id": identifier, "method": method, "params": params}).encode())
        while True:
            reply = self._receive()
            if reply.get("method") == "Runtime.exceptionThrown":
                detail = reply["params"]["exceptionDetails"]
                self.exceptions.append(detail.get("exception", {}).get("description", detail.get("text")))
            if reply.get("id") == identifier:
                if "error" in reply:
                    raise RuntimeError(f"{method}: {reply['error']}")
                return reply.get("result", {})

    def evaluate(self, expression):
        result = self.call("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in result:
            raise RuntimeError(str(result["exceptionDetails"]))
        return result["result"].get("value")

    def navigate(self, url):
        self.exceptions.clear()
        self.call("Page.navigate", url=url)
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            ready = self.evaluate("document.readyState === 'complete' && location.href !== 'about:blank'")
            if ready:
                break
            time.sleep(0.05)
        self.evaluate("document.fonts.ready.then(() => true)")
        # Catalog rendering is asynchronous; wait for its loading message to finish.
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and self.evaluate(
            "!!document.querySelector('#catalog-count')?.textContent.includes('Ielādē')"
        ):
            time.sleep(0.05)
        time.sleep(0.08)

    def screenshot(self, path, full_page=True):
        data = self.call("Page.captureScreenshot", format="png", captureBeyondViewport=full_page,
                         fromSurface=True)["data"]
        path.write_bytes(base64.b64decode(data))


AUDIT = r"""(() => {
    const rendered = el => {
        const r = el.getBoundingClientRect(), s = getComputedStyle(el);
        return r.width > 2 && r.height > 2 && s.visibility === 'visible' && s.display !== 'none'
            && !el.closest('[hidden], [aria-hidden="true"]')
            && !(s.clipPath !== 'none' || (s.position === 'absolute' && r.width < 3));
    };
    const description = el => ({tag:el.tagName.toLowerCase(), id:el.id, class:el.className,
        text:(el.innerText || el.value || el.placeholder || '').trim().slice(0,110)});
    const rgba = color => {
        const v = color.match(/[\d.]+/g)?.map(Number);
        return v?.length >= 3 ? [...v.slice(0,3), v.length > 3 ? v[3] : 1] : [0,0,0,0];
    };
    const over = (fg,bg) => [0,1,2].map(i=>fg[i]*fg[3]+bg[i]*(1-fg[3])).concat(1);
    const background = el => {
        const chain=[];
        for(let p=el;p;p=p.parentElement) chain.unshift(p);
        let bg=[255,255,255,1], uncertain=false;
        for(const p of chain){const s=getComputedStyle(p); bg=over(rgba(s.backgroundColor),bg);
            if(s.backgroundImage!=='none') uncertain=true;}
        return {bg,uncertain};
    };
    const luminance = c => c.slice(0,3).map(x=>x/255).map(x=>x<=0.04045?x/12.92:((x+0.055)/1.055)**2.4)
        .reduce((sum,x,i)=>sum+x*[0.2126,0.7152,0.0722][i],0);
    const ratio = (a,b) => {const x=luminance(a),y=luminance(b);return (Math.max(x,y)+0.05)/(Math.min(x,y)+0.05);};
    const contrast=[], uncertain=[], seen=new Set();
    const check = (el,text,pseudo=null) => {
        if(!rendered(el)||el.closest('button:disabled, input:disabled, select:disabled, textarea:disabled')) return;
        const s=getComputedStyle(el,pseudo), {bg,uncertain:unknown}=background(el);
        const fg=over(rgba(s.color),bg), value=ratio(fg,bg);
        const large=parseFloat(s.fontSize)>=24||(parseFloat(s.fontSize)>=18.66&&parseInt(s.fontWeight)>=700);
        const required=large?3:4.5, key=[s.color,bg.join(','),required,text.slice(0,80)].join('|');
        if(seen.has(key))return; seen.add(key);
        if(unknown){uncertain.push({...description(el),text:text.slice(0,110)});return;}
        if(value+0.005<required)contrast.push({...description(el),text:text.slice(0,110),
            ratio:Math.round(value*100)/100,required,foreground:s.color,background:bg.slice(0,3),pseudo});
    };
    const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
    while(walker.nextNode()){const n=walker.currentNode;
        if(n.textContent.trim()&&!n.parentElement.closest('script,style,svg,option'))check(n.parentElement,n.textContent.trim());}
    for(const el of document.querySelectorAll('input:not([type=hidden]),textarea,select')) {
        if(el.value)check(el,el.value);
        if(el.placeholder&&!el.value)check(el,el.placeholder,'::placeholder');
    }
    const overflow=[];
    for(const el of document.body.querySelectorAll('*')){
        if(!rendered(el))continue;
        const r=el.getBoundingClientRect();
        if(r.right<=document.documentElement.clientWidth+1&&r.left>=-1)continue;
        let contained=false;
        for(let p=el.parentElement;p&&p!==document.body;p=p.parentElement){
            if(['auto','scroll'].includes(getComputedStyle(p).overflowX)&&p.clientWidth<p.scrollWidth){contained=true;break;}}
        if(!contained)overflow.push({...description(el),left:Math.round(r.left),right:Math.round(r.right)});
    }
    const unlabeled=[...document.querySelectorAll('input:not([type=hidden]):not([type=submit]),select,textarea')]
        .filter(el=>rendered(el)&&!el.labels?.length&&!el.getAttribute('aria-label')&&!el.getAttribute('aria-labelledby'))
        .map(description);
    const text=document.body.innerText;
    const overflowSources=document.documentElement.scrollWidth>document.documentElement.clientWidth+1 ? [...document.querySelectorAll('*')]
        .filter(el=>el.scrollWidth>el.clientWidth+2&&el.clientWidth>0)
        .map(el=>({...description(el),clientWidth:el.clientWidth,scrollWidth:el.scrollWidth,
            overflowX:getComputedStyle(el).overflowX,position:getComputedStyle(el).position,
            rectRight:Math.round(el.getBoundingClientRect().right)})).slice(0,30) : [];
    return {title:document.title,url:location.pathname+location.search,lang:document.documentElement.lang,
        viewport:innerWidth,documentWidth:document.documentElement.scrollWidth,
        horizontalOverflow:document.documentElement.scrollWidth>document.documentElement.clientWidth+1,overflow:overflow.slice(0,30),
        overflowSources,
        contrast,uncertainBackgrounds:uncertain.slice(0,20),unlabeled,
        imagesWithoutAlt:[...document.images].filter(el=>!el.hasAttribute('alt')).map(el=>el.src),
        brokenImages:[...document.images].filter(el=>rendered(el)&&el.complete&&!el.naturalWidth).map(el=>el.src),
        englishErrors:/Please log in|Not Found|Forbidden|Bad Request|Internal Server Error|Method Not Allowed/.test(text),
        mainCount:document.querySelectorAll('main').length,footerCount:document.querySelectorAll('footer').length,
        buttons:[...document.querySelectorAll('button, input[type=submit]')].filter(rendered).length};
})()"""


class Inputs(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.values = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "input" and values.get("name"):
            self.values[values["name"]] = values.get("value", "")


def seeded_app(directory, stress=False):
    from flask import flash, render_template
    from backend.app import create_app
    from backend.app.extensions import db
    from backend.app.models import Cart, CartItem, Category, Offer, Order, Product, Supplier, User
    from backend.app.services.demo_data import seed_demo_data, USER_EMAIL

    app = create_app({"TESTING": True, "SECRET_KEY": "disposable-ui-audit-only",
                      "SQLALCHEMY_DATABASE_URI": "sqlite:///" + (directory / "audit.sqlite").as_posix()})

    # These fixtures exist only in this disposable audit process, never in the app.
    @app.get("/__ui/shopping-error")
    def audit_shopping_error():
        return render_template("shopping_error.html"), 503

    @app.get("/__ui/notices")
    def audit_notices():
        flash("Pirmais pārbaudes paziņojums.", "success")
        flash("Otrais pārbaudes paziņojums.", "error")
        return render_template("index.html")

    with app.app_context():
        db.create_all()
        seed_demo_data("DemoAdmin123!", "DemoUser123!")
        db.session.commit()
        users = {user.role: user.id for user in db.session.scalars(db.select(User))}
        empty = User(email="empty.ui@stockflow.test", full_name="Tukšā profila pārbaude", role="user")
        empty.set_password("EmptyUi123!")
        db.session.add(empty)
        db.session.commit()
        users["empty"] = empty.id
        identifiers = {name: db.session.scalar(db.select(model.id).order_by(model.id))
                       for name, model in (("product", Product), ("offer", Offer), ("supplier", Supplier), ("category", Category))}
        buyer = db.session.scalar(db.select(User).where(User.email == USER_EMAIL))
        cart = buyer.cart
        original_items = [(item.offer_id, item.quantity) for item in cart.items]
        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"], session["_fresh"] = str(buyer.id), True
        checkout = client.get("/orders/checkout")
        values = Inputs(checkout.get_data(as_text=True)).values
        response = client.post("/orders/checkout", data={"csrf_token": values["csrf_token"],
            "review_token": values["review_token"], "delivery_address": "Pārbaudes iela 1, Rīga"})
        if response.status_code != 302 or not response.location.startswith("/orders/"):
            raise RuntimeError("Could not create the audit order through the existing checkout")
        identifiers["order"] = db.session.scalar(db.select(Order.id))
        for offer_id, quantity in original_items:
            db.session.add(CartItem(cart_id=cart.id, offer_id=offer_id, quantity=quantity))
        if stress:
            product = db.session.get(Product, identifiers["product"])
            product.name = ("Daudzfunkcionāls profesionālais aprīkojums uzņēmuma noliktavas ikdienas darbam " * 4)[:250]
            product.image_url = "/static/qa-missing-product-image.png"
            supplier = db.session.get(Supplier, identifiers["supplier"])
            supplier.name = ("Profesionālo preču un loģistikas pakalpojumu piegādātājs " * 5)[:250]
            supplier.name_key = supplier.name.casefold()
            for offer in supplier.offers:
                offer.supplier_name = supplier.name
            db.session.get(Offer, identifiers["offer"]).unit_price = "99999999.99"
            for index in range(80):
                db.session.add(Product(sku=f"UI-STRESS-{index:03}", name=f"Pārbaudes prece {index+1}",
                    category_id=identifiers["category"], unit="gab.", is_active=True))
        db.session.commit()
    return app, users, identifiers


def pages(ids):
    p, s, o, c, order = (ids[key] for key in ("product", "supplier", "offer", "category", "order"))
    guest = [("home", "/"), ("catalog", "/catalog/page"), ("catalog-empty", "/catalog/page?q=nav-tādas-preces"),
             ("product", f"/catalog/products/{p}"), ("product-error", f"/catalog/products/{p}?quantity=0"),
             ("login", "/auth/login"), ("register", "/auth/register"), ("login-required", "/cart"),
             ("not-found", "/neeksistejosa-lapa"), ("shopping-error", "/__ui/shopping-error")]
    user = [("profile", "/auth/profile"), ("cart", "/cart"), ("checkout", "/orders/checkout"),
            ("orders", "/orders"), ("orders-empty", "/orders?status=noraidīts"),
            ("order", f"/orders/{order}"), ("forbidden", "/admin")]
    empty = [("empty-profile", "/auth/profile"), ("empty-cart", "/cart"), ("empty-orders", "/orders")]
    admin = [("dashboard", "/admin"), ("applications", "/admin/orders"),
        ("application", f"/admin/orders/{order}"), ("suppliers", "/admin/suppliers"),
        ("supplier-new", "/admin/suppliers/new"), ("supplier", f"/admin/suppliers/{s}"),
        ("supplier-edit", f"/admin/suppliers/{s}/edit"), ("supplier-delete", f"/admin/suppliers/{s}/delete"),
        ("products", "/admin/products"), ("product-new", "/admin/products/new"),
        ("product-new-context", f"/admin/products/new?supplier_id={s}"), ("product", f"/admin/products/{p}"),
        ("product-edit", f"/admin/products/{p}/edit"), ("product-delete", f"/admin/products/{p}/delete"),
        ("offers", "/admin/supplier-products"), ("offer-new", "/admin/supplier-products/new"),
        ("offer-edit", f"/admin/supplier-products/{o}/edit"), ("offer-delete", f"/admin/supplier-products/{o}/delete"),
        ("categories", "/admin/categories"), ("category-new", "/admin/categories/new"),
        ("category-edit", f"/admin/categories/{c}/edit"), ("import-json", "/admin/import/json"),
        ("import-csv", "/admin/import/csv")]
    return [(role, name, path) for role, routes in (("guest", guest), ("user", user), ("empty", empty), ("admin", admin))
            for name, path in routes]


def browser_path(explicit):
    candidates = [explicit, os.getenv("CHROME_PATH"), shutil.which("google-chrome"), shutil.which("chromium"),
                  r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                  r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise RuntimeError("Chromium not found; pass --browser /path/to/chrome")


def report_summary(results):
    return {"checks": len(results), "pages": len({(r["role"], r["page"]) for r in results}),
        "overflow": sum(r.get("horizontalOverflow", False) or bool(r.get("overflow")) for r in results),
        "contrast": sum(bool(r.get("contrast")) for r in results),
        "unlabeled": sum(bool(r.get("unlabeled")) for r in results),
        "englishErrors": sum(r.get("englishErrors", False) for r in results),
        "scriptErrors": sum(bool(r.get("scriptErrors")) for r in results),
        "errors": sum(bool(r.get("error")) for r in results)}


def interactions(cdp, base, ids, app, output):
    """Exercise actual browser event handlers and submitted forms after screenshots."""
    checks=[]

    def record(name, passed, detail=None):
        checks.append({"name":name,"passed":bool(passed),"detail":detail})
        print(f"interaction {name}: {'PASS' if passed else 'FAIL'}",flush=True)

    def wait_for(expression, timeout=12):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:
                if cdp.evaluate(expression):return True
            except RuntimeError:
                pass  # A native form submit replaces its JavaScript execution context.
            time.sleep(0.05)
        return False

    def submit(selector, values=None, button=None):
        expression="(() => {const form=document.querySelector("+json.dumps(selector)+");"
        for name,value in (values or {}).items():
            expression+="form.elements.namedItem("+json.dumps(name)+").value="+json.dumps(value)+";"
            expression+="form.elements.namedItem("+json.dumps(name)+").dispatchEvent(new Event('input',{bubbles:true}));"
        expression+=("form.querySelector("+json.dumps(button)+").click();" if button else "form.requestSubmit();")
        cdp.evaluate(expression+"return true;})()")
        time.sleep(0.15)

    def login(email,password,destination):
        cdp.navigate(base+"/auth/logout")
        cdp.navigate(base+"/auth/login")
        submit(".account-form",{"email":email,"password":password})
        return wait_for("document.readyState==='complete' && (location.pathname.replace(/\\/$/,'')||'/')==="+json.dumps(destination))

    try:
        cdp.call("Emulation.setDeviceMetricsOverride",width=375,height=900,deviceScaleFactor=1,mobile=False)
        cdp.call("Network.clearBrowserCookies")
        cdp.navigate(base+"/")
        cdp.evaluate("document.querySelector('.nav-toggle').click()")
        record("mobile-menu",cdp.evaluate("document.querySelector('.nav-toggle').getAttribute('aria-expanded')==='true' && getComputedStyle(document.querySelector('#site-navigation')).display!=='none' && document.documentElement.scrollWidth<=innerWidth+1"))
        cdp.evaluate("Promise.all(document.querySelector('.market-header').getAnimations({subtree:true}).map(animation=>animation.finished.catch(()=>{})))")
        cdp.screenshot(output/"screenshots"/"mobile-menu-open.png")
        record("mobile-menu-vertical",cdp.evaluate("""(() => {
            const links=[...document.querySelectorAll('#site-navigation > a')];
            return links.every((link,index)=>!index || link.getBoundingClientRect().top >= links[index-1].getBoundingClientRect().bottom);
        })()"""))
        cdp.evaluate("document.querySelector('main').click()")
        record("mobile-menu-outside",cdp.evaluate("document.querySelector('.nav-toggle').getAttribute('aria-expanded')==='false' && getComputedStyle(document.querySelector('#site-navigation')).display==='none'"))
        cdp.evaluate("document.querySelector('.nav-toggle').click()")
        cdp.call("Input.dispatchKeyEvent",type="keyDown",key="Escape",code="Escape",windowsVirtualKeyCode=27)
        cdp.call("Input.dispatchKeyEvent",type="keyUp",key="Escape",code="Escape",windowsVirtualKeyCode=27)
        record("mobile-menu-escape",cdp.evaluate("document.querySelector('.nav-toggle').getAttribute('aria-expanded')==='false' && document.activeElement===document.querySelector('.nav-toggle')"))
        cdp.navigate(base+"/")
        cdp.call("Input.dispatchKeyEvent",type="keyDown",key="Tab",code="Tab",windowsVirtualKeyCode=9)
        cdp.call("Input.dispatchKeyEvent",type="keyUp",key="Tab",code="Tab",windowsVirtualKeyCode=9)
        record("keyboard-focus",cdp.evaluate("document.activeElement.tagName==='A' && getComputedStyle(document.activeElement).outlineStyle!=='none'"))
        cdp.navigate(base+"/catalog/page")
        record("mobile-filters-collapsed", cdp.evaluate("document.querySelector('#filters-toggle').getAttribute('aria-expanded')==='false' && getComputedStyle(document.querySelector('#catalog-filters')).display==='none'"))
        cdp.evaluate("document.querySelector('#filters-toggle').click()")
        record("mobile-filters-open", cdp.evaluate("document.querySelector('#filters-toggle').getAttribute('aria-expanded')==='true' && getComputedStyle(document.querySelector('#catalog-filters')).display!=='none' && document.documentElement.scrollWidth<=innerWidth+1"))
        cdp.evaluate("Promise.all(document.querySelector('.catalog-filter-panel').getAnimations({subtree:true}).map(animation=>animation.finished.catch(()=>{})))")
        cdp.screenshot(output/"screenshots"/"mobile-filters-open.png")
        cdp.evaluate("document.querySelector('#min-price').value='10';document.querySelector('#filters-toggle').click();document.querySelector('#filters-toggle').click()")
        record("mobile-filters-preserve-values", cdp.evaluate("document.querySelector('#min-price').value==='10'"))
        cdp.evaluate("document.querySelector('#min-price').value='';document.querySelector('#min-price').focus()")
        cdp.call("Input.dispatchKeyEvent",type="keyDown",key="Escape",code="Escape",windowsVirtualKeyCode=27)
        cdp.call("Input.dispatchKeyEvent",type="keyUp",key="Escape",code="Escape",windowsVirtualKeyCode=27)
        record("mobile-filters-escape", cdp.evaluate("document.querySelector('#filters-toggle').getAttribute('aria-expanded')==='false' && document.activeElement===document.querySelector('#filters-toggle')"))
        cdp.evaluate("document.querySelector('#filters-toggle').click()")
        submit("#catalog-search-form",{"q":"neeksistējoša-pārbaudes-prece"})
        record("catalog-search-empty",wait_for("document.querySelector('#catalog-count').textContent==='0 preces' && new URLSearchParams(location.search).get('q')==='neeksistējoša-pārbaudes-prece'"))
        cdp.evaluate("document.querySelector('#clear-filters').click()")
        record("catalog-clear",wait_for("document.querySelectorAll('.product-card').length>0 && !location.search"))
        cdp.evaluate("document.querySelector('#min-price').value='100';document.querySelector('#max-price').value='1';document.querySelector('#apply-filters').click()")
        record("catalog-filter-validation",wait_for("""document.querySelector('#max-price').getAttribute('aria-invalid')==='true'
            && document.querySelector('#max-price').getAttribute('aria-errormessage')==='catalog-message'
            && document.querySelector('#filters-toggle').getAttribute('aria-expanded')==='true'
            && document.querySelector('#catalog-message').classList.contains('is-error')
            && document.querySelector('#catalog-message').textContent.includes('Maksimālā cena nedrīkst būt mazāka')
            && document.querySelector('.catalog-content').getAttribute('aria-busy')==='false'"""))
        cdp.screenshot(output/"screenshots"/"catalog-filter-error.png")
        cdp.evaluate("document.querySelector('#clear-filters').click()")
        record("catalog-validation-clear",wait_for("""document.querySelectorAll('.product-card').length>0
            && !document.querySelector('#catalog-filters [aria-invalid=true]')
            && !document.querySelector('#catalog-message').classList.contains('is-error')
            && document.querySelector('#catalog-retry').hidden"""))
        cdp.call("Network.enable")
        try:
            cdp.call("Network.setBlockedURLs",urls=[base+"/catalog?*"])
            cdp.evaluate("document.querySelector('#apply-filters').click()")
            record("catalog-network-error",wait_for("""document.querySelector('#catalog-count').textContent==='Kļūda'
                && document.querySelector('#catalog-message').classList.contains('is-error')
                && document.querySelector('#catalog-message').textContent.includes('Pārbaudiet savienojumu')
                && !document.querySelector('#catalog-retry').hidden
                && !document.querySelector('.product-card')
                && document.querySelector('.catalog-content').getAttribute('aria-busy')==='false'"""))
            cdp.screenshot(output/"screenshots"/"catalog-network-error.png")
        finally:
            cdp.call("Network.setBlockedURLs",urls=[])
        cdp.evaluate("document.querySelector('#catalog-retry').click()")
        record("catalog-network-retry",wait_for("""document.querySelectorAll('.product-card').length>0
            && document.querySelector('#catalog-retry').hidden
            && !document.querySelector('#catalog-message').classList.contains('is-error')
            && document.querySelector('.catalog-content').getAttribute('aria-busy')==='false'"""))
        cdp.evaluate("const select=document.querySelector('#sort-control');select.value='name-desc';select.dispatchEvent(new Event('change',{bubbles:true}));")
        record("catalog-sort",cdp.evaluate("(() => {const names=[...document.querySelectorAll('.product-card h3')].map(n=>n.textContent);return names.every((name,i)=>!i||names[i-1].localeCompare(name,'lv')>=0);})()"))
        cdp.evaluate("const category=document.querySelector('#category-filter');category.selectedIndex=1;category.dispatchEvent(new Event('change',{bubbles:true}));")
        record("category-filter",wait_for("!!new URLSearchParams(location.search).get('category_id') && !document.querySelector('#catalog-count').textContent.includes('Ielādē')"))
        cdp.evaluate("document.querySelector('#category-filter').value='';document.querySelector('#supplier-filter').value='dte';document.querySelector('#apply-filters').click()")
        record("supplier-filter",wait_for("Number.parseInt(document.querySelector('#catalog-count').textContent)>0 && new URLSearchParams(location.search).get('supplier')==='dte'"))
        record("mobile-filters-apply-closes", wait_for("document.querySelector('#filters-toggle').getAttribute('aria-expanded')==='false' && document.activeElement===document.querySelector('#filters-toggle')"))
        cdp.call("Emulation.setDeviceMetricsOverride",width=1024,height=900,deviceScaleFactor=1,mobile=False)
        record("desktop-filters-visible", wait_for("getComputedStyle(document.querySelector('#catalog-filters')).display!=='none' && getComputedStyle(document.querySelector('#filters-toggle')).display==='none'"))
        cdp.call("Emulation.setDeviceMetricsOverride",width=375,height=900,deviceScaleFactor=1,mobile=False)
        record("mobile-filters-resize", wait_for("getComputedStyle(document.querySelector('#catalog-filters')).display==='none' && document.querySelector('#supplier-filter').value==='dte'"))
        cdp.navigate(base+"/auth/login")
        cdp.evaluate("document.querySelector('.account-form').requestSubmit()")
        record("latvian-native-validation",cdp.evaluate("document.querySelector('#email').validationMessage==='Lūdzu, aizpildiet šo lauku.'"))
        record("buyer-login",login("user.demo@stockflow.test","DemoUser123!","/"))
        cdp.navigate(base+f"/catalog/products/{ids['product']}")
        cdp.evaluate("const q=document.querySelector('#compare-quantity');q.value='3';q.dispatchEvent(new Event('change',{bubbles:true}));")
        record("comparison-autosubmit",wait_for("new URLSearchParams(location.search).get('quantity')==='3' && document.readyState==='complete'"))
        cdp.evaluate("const s=document.querySelector('#compare-sort');s.value='delivery';s.dispatchEvent(new Event('change',{bubbles:true}));")
        record("comparison-sort",wait_for("new URLSearchParams(location.search).get('sort')==='delivery' && document.readyState==='complete'"))
        cdp.evaluate("document.querySelector('#clear-comparison-filters').click()")
        record("comparison-clear",wait_for("!location.search && document.readyState==='complete' && document.querySelector('#compare-quantity').value==='1' && document.querySelector('#compare-sort').value==='total-asc'"))
        cdp.evaluate("document.querySelector('.offer-order-form button:not(:disabled)').click()")
        record("add-to-cart",wait_for("document.body.innerText.includes('pievienoti grozam') && document.readyState==='complete'"))
        cdp.navigate(base+"/cart")
        quantity=cdp.evaluate("(() => {const q=document.querySelector('.cart-quantity-form input[name=quantity]');return String(Math.min(Number(q.max),Number(q.min)+1));})()")
        submit(".cart-quantity-form",{"quantity":quantity})
        record("cart-quantity",wait_for("document.body.innerText.includes('Daudzums grozā atjaunināts.') && document.readyState==='complete'"))
        cdp.navigate(base+"/orders/checkout")
        cdp.call("Emulation.setDeviceMetricsOverride",width=1440,height=720,deviceScaleFactor=1,mobile=False)
        record("checkout-summary-static",cdp.evaluate("(() => {const s=document.querySelector('.checkout-summary'),top=s.getBoundingClientRect().top+scrollY;window.scrollBy(0,240);return getComputedStyle(s).position==='static' && Math.abs(s.getBoundingClientRect().top+scrollY-top)<2;})()"))
        cdp.call("Emulation.setDeviceMetricsOverride",width=375,height=900,deviceScaleFactor=1,mobile=False)
        cdp.evaluate("window.scrollTo(0,0)")
        submit("#checkout-submit",{"note":"Pārlūka pārbaudes pieteikums"})
        created=wait_for("/^\\/orders\\/\\d+$/.test(location.pathname) && document.readyState==='complete'")
        record("checkout-submit",created)
        record("submission-toast",cdp.evaluate("[...document.querySelectorAll('.toast-stack [data-toast]')].some(t=>t.textContent.includes('Pieteikums saņemts.')) && !document.querySelector('.receipt-notice') && getComputedStyle(document.querySelector('.toast-stack')).position==='fixed'"))
        cdp.evaluate("Promise.all(document.querySelector('.toast-stack').getAnimations({subtree:true}).map(a=>a.finished.catch(()=>{})))")
        cdp.screenshot(output/"screenshots"/"submission-toast.png",full_page=False)
        cdp.call("Emulation.setDeviceMetricsOverride",width=160,height=450,deviceScaleFactor=2,mobile=False)
        cdp.evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
        record("submission-toast-small-screen",cdp.evaluate("(() => {const s=document.querySelector('.toast-stack').getBoundingClientRect();return s.top>=-1 && s.bottom<=innerHeight+1 && document.documentElement.scrollWidth<=document.documentElement.clientWidth+1;})()"))
        cdp.screenshot(output/"screenshots"/"submission-toast-320-z2.png",full_page=False)
        record("submission-toast-dismisses",wait_for("![...document.querySelectorAll('[data-toast]')].some(t=>t.textContent.includes('Pieteikums saņemts.'))",timeout=12))
        order=cdp.evaluate("location.pathname.split('/').pop()") if created else str(ids["order"])
        cdp.call("Emulation.setDeviceMetricsOverride",width=1024,height=720,deviceScaleFactor=1,mobile=False)
        cdp.navigate(base+"/orders/"+order)
        cdp.evaluate("const summary=document.querySelector('.order-receipt .shopping-summary');window.scrollTo(0,summary.getBoundingClientRect().top+scrollY-24)")
        record("order-summary-sticky",cdp.evaluate("Math.abs(document.querySelector('.order-receipt .shopping-summary').getBoundingClientRect().top-24)<2"))
        cdp.call("Emulation.setDeviceMetricsOverride",width=375,height=900,deviceScaleFactor=1,mobile=False)
        cdp.navigate(base+"/auth/profile")
        for target in ("profile-notifications-content", "profile-orders-content"):
            toggle = '[aria-controls="'+target+'"]'
            record(target+"-collapsed", cdp.evaluate("document.querySelector("+json.dumps(toggle)+").getAttribute('aria-expanded')==='false' && getComputedStyle(document.getElementById("+json.dumps(target)+")).display==='none'"))
            cdp.evaluate("document.querySelector("+json.dumps(toggle)+").click()")
            record(target+"-open", cdp.evaluate("document.querySelector("+json.dumps(toggle)+").getAttribute('aria-expanded')==='true' && getComputedStyle(document.getElementById("+json.dumps(target)+")).display!=='none' && document.documentElement.scrollWidth<=innerWidth+1"))
            cdp.evaluate("document.querySelector("+json.dumps(toggle)+").focus()")
            cdp.call("Input.dispatchKeyEvent",type="keyDown",key="Escape",code="Escape",windowsVirtualKeyCode=27)
            cdp.call("Input.dispatchKeyEvent",type="keyUp",key="Escape",code="Escape",windowsVirtualKeyCode=27)
            record(target+"-escape", cdp.evaluate("document.querySelector("+json.dumps(toggle)+").getAttribute('aria-expanded')==='false' && document.activeElement===document.querySelector("+json.dumps(toggle)+")"))
            cdp.evaluate("document.querySelector("+json.dumps(toggle)+").click()")
        cdp.screenshot(output/"screenshots"/"mobile-profile-sections-open.png")
        record("profile-notification",cdp.evaluate("document.body.innerText.includes('Pieteikums #'+"+json.dumps(order)+"+' iesniegts')"))
        cdp.evaluate("[...document.querySelectorAll('.notification-row a')].find(link=>link.textContent.includes('Pieteikums #'+"+json.dumps(order)+")).click()")
        opened = wait_for("location.pathname==='/orders/'+"+json.dumps(order)+" && document.readyState==='complete'")
        cdp.navigate(base+"/auth/profile")
        # Citiem pieteikumiem drīkst palikt nelasīti paziņojumi; pārbaudām tieši atvērto.
        read = cdp.evaluate("""(() => {
            const link = [...document.querySelectorAll('.notification-row a')]
                .find(link => new URL(link.href).pathname === '/orders/' + """ + json.dumps(order) + """);
            return !!link && !link.closest('.notification-row').classList.contains('notification-unread');
        })()""")
        record("notification-auto-read", opened and read)
        submit(".password-change-form",{"current_password":"WrongPassword!","new_password":"BrowserUser123!","new_password_confirmation":"BrowserUser123!"})
        record("password-change-current-validation",wait_for("document.querySelector('#current-password-error')?.textContent.includes('Pašreizējā parole nav pareiza.') && document.querySelector('#current_password').value===''"))
        submit(".password-change-form",{"current_password":"DemoUser123!","new_password":"BrowserUser123!","new_password_confirmation":"BrowserUser123!"})
        record("password-change-success",wait_for("location.pathname==='/auth/profile' && document.body.innerText.includes('Parole veiksmīgi nomainīta.')"))
        record("password-change-login",login("user.demo@stockflow.test","BrowserUser123!","/"))
        record("admin-login",login("admin.demo@stockflow.test","DemoAdmin123!","/admin"))
        record("admin-sections-collapsed",cdp.evaluate("getComputedStyle(document.querySelector('#admin-section-links')).display==='none'"))
        cdp.evaluate("document.querySelector('[aria-controls=admin-section-links]').click()")
        record("admin-sections-open",cdp.evaluate("document.querySelector('[aria-controls=admin-section-links]').getAttribute('aria-expanded')==='true' && getComputedStyle(document.querySelector('#admin-section-links')).display!=='none' && document.querySelector('#admin-section-links [aria-current=page]').textContent==='Pārskats' && document.documentElement.scrollWidth<=innerWidth+1"))
        cdp.screenshot(output/"screenshots"/"mobile-admin-sections-open.png")
        cdp.call("Emulation.setDeviceMetricsOverride",width=1024,height=900,deviceScaleFactor=1,mobile=False)
        record("admin-sections-desktop",wait_for("getComputedStyle(document.querySelector('#admin-section-links')).display!=='none' && getComputedStyle(document.querySelector('[aria-controls=admin-section-links]')).display==='none'"))
        cdp.call("Emulation.setDeviceMetricsOverride",width=375,height=900,deviceScaleFactor=1,mobile=False)
        record("admin-sections-resize",wait_for("document.querySelector('[aria-controls=admin-section-links]').getAttribute('aria-expanded')==='false' && getComputedStyle(document.querySelector('#admin-section-links')).display==='none'"))
        cdp.navigate(base+"/admin/orders/"+order)
        cdp.call("Emulation.setDeviceMetricsOverride",width=1440,height=900,deviceScaleFactor=1,mobile=False)
        record("admin-review-two-columns",cdp.evaluate("(() => {const c=document.querySelector('.cart-layout > .supplier-groups').getBoundingClientRect(),s=document.querySelector('.admin-review-summary').getBoundingClientRect();return s.left>=c.right+20 && s.top<c.bottom;})()"))
        cdp.call("Emulation.setDeviceMetricsOverride",width=375,height=900,deviceScaleFactor=1,mobile=False)
        submit("form.admin-form",button="button[value=decline]")
        record("decline-reason-toast",wait_for("[...document.querySelectorAll('.toast-stack [data-toast]')].some(t=>t.textContent.includes('Lai noraidītu pieteikumu')) && document.querySelector('#admin_note').getAttribute('aria-invalid')==='true'"))
        record("decision-actions-gap",cdp.evaluate("(() => {const a=document.querySelector('button[value=approve]').getBoundingClientRect(),b=document.querySelector('button[value=decline]').getBoundingClientRect();return b.left-a.right>=12 || b.top-a.bottom>=12;})()"))
        cdp.evaluate("Promise.all(document.querySelector('.toast-stack').getAnimations({subtree:true}).map(a=>a.finished.catch(()=>{})))")
        cdp.screenshot(output/"screenshots"/"decline-reason-toast.png",full_page=False)
        cdp.evaluate("document.querySelectorAll('.toast-close').forEach(b=>b.click())")
        submit("form.admin-form",button="button[value=approve]")
        record("admin-approve",wait_for("document.body.innerText.includes('Lēmums saglabāts.') && document.body.innerText.includes('apstiprināts') && document.readyState==='complete'"))
        cdp.navigate(base+"/admin/categories/new")
        submit("form.admin-form",{"name":"Pārlūka dialoga pārbaude","description":"Tukša dzēšama kategorija"})
        record("category-create",wait_for("location.pathname==='/admin/categories' && document.body.innerText.includes('Pārlūka dialoga pārbaude')"))
        for width,zoom,height in ((320,1,640),(375,1,640),(320,2,240)):
            cdp.call("Emulation.setDeviceMetricsOverride",width=round(width/zoom),height=height,
                     deviceScaleFactor=zoom,mobile=False)
            cdp.evaluate("""window.__deleteButton=[...document.querySelectorAll('tr')]
                .find(row=>row.querySelector('.cell-primary')?.textContent==='Pārlūka dialoga pārbaude')
                .querySelector('[data-confirm-delete]');window.__deleteButton.focus();window.__deleteButton.click();""")
            opened=cdp.evaluate("document.querySelector('[data-confirm-dialog]').open && document.activeElement===document.querySelector('#delete-dialog-title')")
            audit=cdp.evaluate(AUDIT)
            bounds=cdp.evaluate("(() => {const dialog=document.querySelector('dialog'),d=dialog.getBoundingClientRect(),h=document.querySelector('#delete-dialog-title').getBoundingClientRect();return {left:d.left,top:d.top,right:d.right,bottom:d.bottom,width:innerWidth,height:innerHeight,titleTop:h.top,titleBottom:h.bottom,clientWidth:dialog.clientWidth,scrollWidth:dialog.scrollWidth};})()")
            fits=(bounds["left"]>=-1 and bounds["top"]>=-1 and bounds["right"]<=bounds["width"]+1
                  and bounds["bottom"]<=bounds["height"]+1 and bounds["titleTop"]>=bounds["top"]
                  and bounds["titleBottom"]<=bounds["bottom"] and bounds["scrollWidth"]<=bounds["clientWidth"]+1)
            record(f"category-dialog-{width}-z{zoom}",opened and fits and not audit["horizontalOverflow"] and not audit["contrast"],
                   {"bounds":bounds,"contrast":audit["contrast"]})
            cdp.screenshot(output/"screenshots"/f"category-dialog-{width}-z{zoom}.png",full_page=False)
            cdp.evaluate("document.querySelector('[data-confirm-cancel]').click()")
            record(f"category-dialog-cancel-{width}-z{zoom}",cdp.evaluate("!document.querySelector('dialog').open && document.activeElement===window.__deleteButton"))
            cdp.evaluate("window.__deleteButton.click()")
            cdp.call("Input.dispatchKeyEvent",type="keyDown",key="Escape",code="Escape",windowsVirtualKeyCode=27)
            cdp.call("Input.dispatchKeyEvent",type="keyUp",key="Escape",code="Escape",windowsVirtualKeyCode=27)
            record(f"category-dialog-escape-{width}-z{zoom}",wait_for("!document.querySelector('dialog').open && document.activeElement===window.__deleteButton"))
        cdp.evaluate("window.__deleteButton.click();document.querySelector('[data-confirm-accept]').click()")
        record("category-dialog-confirm",wait_for("document.readyState==='complete' && !document.body.innerText.includes('Pārlūka dialoga pārbaude') && document.body.innerText.includes('Kategorija veiksmīgi dzēsta.')"))
        cdp.call("Emulation.setDeviceMetricsOverride",width=375,height=900,deviceScaleFactor=1,mobile=False)
        for kind in ("json","csv"):
            cdp.navigate(base+"/admin/import/"+kind)
            result=cdp.evaluate("""(async () => {
                const form=document.querySelector('form.admin-form');
                const data=new FormData(form);
                const response=await fetch(location.href,{method:'POST',body:data});
                return {status:response.status,text:await response.text()};
            })()""")
            record("import-"+kind+"-validation",result["status"]==422 and "Izvēlieties" in result["text"])
            cdp.navigate(base+"/admin/import/"+kind)
            document=cdp.call("DOM.getDocument")["root"]["nodeId"]
            picker=cdp.call("DOM.querySelector",nodeId=document,selector="#import-file")["nodeId"]
            cdp.call("DOM.setFileInputFiles",nodeId=picker,files=[str(ROOT/"data_samples"/("offers_import."+kind))])
            record("import-"+kind+"-picker",cdp.evaluate("document.querySelector('[data-file-name]').textContent==="+json.dumps("offers_import."+kind)))
            submit("form.admin-form")
            record("import-"+kind+"-success",wait_for("document.readyState==='complete' && document.body.innerText.includes("+json.dumps(kind.upper()+" imports pabeigts.")+")"))
        cdp.navigate(base+"/auth/logout")
        cdp.navigate(base+"/auth/register")
        # Pārbaudām katras prasības maiņu, ielīmēšanu un atkārtotu dzēšanu pārlūkā.
        for value, expected in [("", [False, False, False]), ("abcdefgh", [True, False, False]),
                                ("Abcdefgh", [True, True, False]), ("Ābcdefg!", [True, True, True]),
                                ("Abcdefg ", [True, True, False]), ("A!", [False, True, True]),
                                ("", [False, False, False])]:
            state = cdp.evaluate("""(() => {
                const input = document.querySelector('[data-password-input]');
                input.value = """ + json.dumps(value) + """;
                input.dispatchEvent(new Event('input', {bubbles:true}));
                return {met:[...document.querySelectorAll('[data-password-rule]')].map(item=>item.classList.contains('is-met')),
                        valid:input.checkValidity()};
            })()""")
            record("password-requirements-"+str(len(checks)), state['met']==expected and state['valid']==all(expected), state)
        cdp.call("Emulation.setDeviceMetricsOverride",width=1440,height=900,deviceScaleFactor=1,mobile=False)
        record("register-button-full-width",cdp.evaluate("(() => {const f=document.querySelector('.account-form').getBoundingClientRect(),b=document.querySelector('.form-actions > button').getBoundingClientRect();return Math.abs(f.width-b.width)<2;})()"))
        cdp.call("Emulation.setDeviceMetricsOverride",width=375,height=900,deviceScaleFactor=1,mobile=False)
        submit(".account-form",{"full_name":"Pārlūka Pārbaude","email":"browser.ui@stockflow.test",
            "password":"BrowserUi123!","password_confirmation":"BrowserUi123!",
            "company_name":"Pārlūka Pārbaude SIA","registration_no":"40000000002",
            "address":"Pārbaudes iela 2, Rīga"})
        record("registration",wait_for("location.pathname==='/' && document.readyState==='complete' && document.body.innerText.includes('Konts izveidots.')"))
        cdp.navigate(base+"/__ui/notices")
        no_toast_scroll="(() => {const s=document.querySelector('.toast-stack'),t=s.querySelector('[data-toast]:not([hidden])');return getComputedStyle(s).overflowY==='visible' && s.scrollHeight<=s.clientHeight+1 && s.scrollWidth<=s.clientWidth+1 && t.scrollHeight<=t.clientHeight+1 && t.scrollWidth<=t.clientWidth+1;})()"
        record("toast-queue-first",cdp.evaluate("document.querySelectorAll('[data-toast]:not([hidden])').length===1 && document.querySelector('[data-toast]:not([hidden])').textContent.includes('Pirmais')") and cdp.evaluate(no_toast_scroll))
        cdp.evaluate("document.querySelector('[data-toast]:not([hidden]) .toast-close').click()")
        record("toast-queue-next",wait_for("document.querySelectorAll('[data-toast]:not([hidden])').length===1 && document.querySelector('[data-toast]:not([hidden])').textContent.includes('Otrais')") and cdp.evaluate(no_toast_scroll))
        cdp.evaluate("document.querySelector('[data-toast]:not([hidden]) .toast-close').click()")
        record("toast-queue-close",wait_for("!document.querySelector('.toast-stack')"))
        cdp.navigate(base+"/__ui/notices")
        bounds=cdp.evaluate("(() => {const t=document.querySelector('[data-toast]:not([hidden])');t.querySelector('.toast-close').focus();const r=t.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()")
        cdp.call("Input.dispatchMouseEvent",type="mouseMoved",x=bounds["x"],y=bounds["y"])
        record("toast-auto-next-while-hovered-and-focused",wait_for("document.querySelector('[data-toast]:not([hidden])')?.textContent.includes('Otrais')",timeout=12))
        record("toast-auto-close-while-hovered-and-focused",wait_for("!document.querySelector('.toast-stack')",timeout=12))
        # Populate only this disposable account to exercise all three history pages.
        from backend.app.extensions import db
        from backend.app.models import Notification, Order, User
        with app.app_context():
            owner = db.session.scalar(db.select(User).where(User.email == "browser.ui@stockflow.test"))
            page_order_ids = []
            for index in range(12):
                timestamp = datetime(2026, 1, 1) + timedelta(days=index)
                entry = Order(user_id=owner.id, company_profile_id=owner.company_profile.id,
                              total_amount="10.00", created_at=timestamp)
                db.session.add(entry)
                db.session.flush()
                page_order_ids.append(entry.id)
                db.session.add(Notification(user_id=owner.id, order_id=entry.id, kind="submitted",
                    message=f"Lapošanas paziņojums {index + 1:02}", created_at=timestamp))
            db.session.commit()
        cdp.navigate(base+"/auth/profile")
        record("profile-first-five",cdp.evaluate("document.querySelectorAll('.notification-row').length===5 && document.querySelector('.notification-row a').textContent.includes('12') && document.querySelectorAll('.profile-order-row').length===5"))
        cdp.evaluate("document.querySelector('[aria-controls=profile-notifications-content]').click();document.querySelector('[data-profile-pagination=notifications] a[rel=next]').click()")
        record("profile-notifications-next",wait_for("new URLSearchParams(location.search).get('notifications_page')==='2' && document.querySelector('.notification-row a')?.textContent.includes('07') && document.querySelector('[aria-controls=profile-notifications-content]').getAttribute('aria-expanded')==='true'"))
        cdp.screenshot(output/"screenshots"/"profile-notifications-page-2-mobile.png",full_page=False)
        cdp.evaluate("document.querySelector('[aria-controls=profile-orders-content]').click();document.querySelector('[data-profile-pagination=orders] a[rel=next]').click()")
        record("profile-orders-next-independent",wait_for("new URLSearchParams(location.search).get('notifications_page')==='2' && new URLSearchParams(location.search).get('orders_page')==='2' && document.querySelectorAll('.profile-order-row').length===5 && document.querySelector('.profile-order-row').pathname.endsWith('/'+"+json.dumps(str(page_order_ids[6]))+")"))
        cdp.evaluate("document.querySelector('[data-profile-pagination=orders] a[rel=next]').click()")
        record("profile-orders-last-page",wait_for("new URLSearchParams(location.search).get('orders_page')==='3' && document.querySelectorAll('.profile-order-row').length===2 && !document.querySelector('[data-profile-pagination=orders] a[rel=next]') && document.querySelector('.notification-row a').textContent.includes('07')"))
        cdp.evaluate("document.querySelector('[aria-controls=profile-notifications-content]').click();document.querySelector('[data-profile-pagination=notifications] a[rel=next]').click()")
        record("profile-notifications-last-page",wait_for("new URLSearchParams(location.search).get('notifications_page')==='3' && new URLSearchParams(location.search).get('orders_page')==='3' && document.querySelectorAll('.notification-row').length===2 && !document.querySelector('[data-profile-pagination=notifications] a[rel=next]')"))
        cdp.evaluate("document.querySelector('[data-profile-pagination=notifications] a[rel=prev]').click()")
        record("profile-previous-preserves-other-page",wait_for("new URLSearchParams(location.search).get('notifications_page')==='2' && new URLSearchParams(location.search).get('orders_page')==='3' && document.querySelector('.notification-row a')?.textContent.includes('07')"))
        cdp.call("Emulation.setDeviceMetricsOverride",width=1440,height=900,deviceScaleFactor=1,mobile=False)
        cdp.evaluate("window.scrollTo(0,0)")
        cdp.screenshot(output/"screenshots"/"profile-pagination-desktop.png")
        cdp.call("Emulation.setDeviceMetricsOverride",width=160,height=450,deviceScaleFactor=2,mobile=False)
        cdp.navigate(base+"/auth/profile?notifications_page=3&orders_page=3#profile-notifications-content")
        paging_audit=cdp.evaluate(AUDIT)
        record("profile-pagination-320-z2",not paging_audit["horizontalOverflow"] and not paging_audit["contrast"] and not paging_audit["unlabeled"],paging_audit)
    except Exception as error:
        record("interaction-exception",False,str(error))
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", help="Installed Chromium executable")
    parser.add_argument("--browser-no-sandbox", action="store_true",
                        help="Disable Chromium sandbox only for isolated local QA in restricted environments")
    parser.add_argument("--widths", nargs="+", type=int, default=[320,375,425,768,1024,1440,1920])
    parser.add_argument("--zooms", nargs="+", type=float, default=[1,2], help="Effective browser zoom factors")
    parser.add_argument("--roles", nargs="+", choices=["guest","user","empty","admin"])
    parser.add_argument("--pages", nargs="+", help="Page names to include, e.g. catalog cart product-edit")
    parser.add_argument("--screenshots", choices=["all","representative","none"], default="representative")
    parser.add_argument("--stress", action="store_true", help="Long names, maximum unit price and 80 extra products")
    parser.add_argument("--interactions", action="store_true", help="Also exercise navigation, forms, catalog, cart, checkout and approval")
    parser.add_argument("--output", type=Path, default=ROOT / "instance" / "ui-qa" / datetime.now().strftime("%Y%m%d-%H%M%S"))
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "screenshots").mkdir(exist_ok=True)
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    from werkzeug.serving import make_server

    results=[]
    with tempfile.TemporaryDirectory(prefix="stockflow-ui-") as temporary:
        directory=Path(temporary)
        app,users,ids=seeded_app(directory,args.stress)
        server=make_server("127.0.0.1",0,app,threaded=True)
        base=f"http://127.0.0.1:{server.server_port}"
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        profile=directory/"chromium"
        browser_log=(args.output/"browser.log").open("wb")
        browser_flags = ["--disable-gpu"]
        if args.browser_no_sandbox:
            browser_flags.append("--no-sandbox")
        process=subprocess.Popen([browser_path(args.browser),*browser_flags,"--headless=new","--no-first-run",
            "--no-default-browser-check","--disable-background-networking","--disable-sync",
            "--remote-debugging-port=0",f"--user-data-dir={profile}","about:blank"],
            stdout=subprocess.DEVNULL,stderr=browser_log)
        cdp=None
        try:
            deadline=time.monotonic()+25
            active=profile/"DevToolsActivePort"
            while not active.exists() and time.monotonic()<deadline:
                if process.poll() is not None:raise RuntimeError("Chromium exited before DevTools started")
                time.sleep(0.1)
            port=int(active.read_text().splitlines()[0])
            with urlopen(f"http://127.0.0.1:{port}/json/list") as response:
                targets=json.load(response)
            cdp=CDP(next(t["webSocketDebuggerUrl"] for t in targets if t["type"]=="page"))
            cdp.call("Page.enable")
            cdp.call("Runtime.enable")
            selected=[p for p in pages(ids) if (not args.roles or p[0] in args.roles) and (not args.pages or p[1] in args.pages)]
            previous_role=None
            for role,name,path in selected:
                if role!=previous_role:
                    cdp.call("Network.clearBrowserCookies")
                    if role!="guest":
                        cookie=app.session_interface.get_signing_serializer(app).dumps({"_user_id":str(users[role]),"_fresh":True})
                        cdp.call("Network.setCookie",name=app.config["SESSION_COOKIE_NAME"],value=cookie,url=base,httpOnly=True)
                    previous_role=role
                for zoom in args.zooms:
                    for width in args.widths:
                        cdp.call("Emulation.setDeviceMetricsOverride",width=round(width/zoom),height=round(900/zoom),
                                 deviceScaleFactor=zoom,mobile=False)
                        label=f"{role}-{name}-{width}-z{zoom:g}"
                        try:
                            cdp.navigate(base+path)
                            audit=cdp.evaluate(AUDIT)
                            audit.update(role=role,page=name,width=width,zoom=zoom,scriptErrors=list(cdp.exceptions))
                            save=args.screenshots=="all" or (args.screenshots=="representative" and width in (375,1440) and zoom==1)
                            if save:
                                filename=label+".png"
                                cdp.screenshot(args.output/"screenshots"/filename)
                                audit["screenshot"]="screenshots/"+filename
                            results.append(audit)
                        except Exception as error:
                            results.append({"role":role,"page":name,"width":width,"zoom":zoom,"error":str(error)})
                        (args.output/"report.json").write_text(json.dumps({"summary":report_summary(results),
                            "stress":args.stress,"results":results},ensure_ascii=False,indent=2),encoding="utf-8")
                print(f"{role:5} {name:22} {len(args.widths)*len(args.zooms):2} checks",flush=True)
            functional=interactions(cdp,base,ids,app,args.output) if args.interactions else []
            (args.output/"report.json").write_text(json.dumps({"summary":report_summary(results),
                "stress":args.stress,"results":results,"interactions":functional},ensure_ascii=False,indent=2),encoding="utf-8")
            print(json.dumps(report_summary(results),ensure_ascii=False),flush=True)
            print(f"Report: {args.output/'report.json'}",flush=True)
        finally:
            if cdp:
                cdp.sock.close()
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            browser_log.close()
            server.shutdown()
            with app.app_context():
                from backend.app.extensions import db
                db.session.remove()
                db.engine.dispose()
    summary=report_summary(results)
    return int(any(summary[key] for key in ("overflow","contrast","unlabeled","englishErrors","scriptErrors","errors"))
               or any(not check["passed"] for check in functional))


if __name__=="__main__":
    raise SystemExit(main())
