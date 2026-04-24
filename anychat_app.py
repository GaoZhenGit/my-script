import sys
import tools
from seleniumbase import BaseCase

BaseCase.main(__name__, __file__, "--edge")


class CustomBaseCase(BaseCase):
    """扩展 BaseCase，自动等待Ajax加载完成"""

    def wait_for_ajax_complete(self):
        """等待Ajax加载完成"""
        self.wait_for_element_not_visible("#AjaxLoading", timeout=10)

    def ensure_checkbox_checked(self, label_selector):
        """确保复选框被勾选，如果未勾选则点击"""
        self.wait_for_ajax_complete()
        is_checked = self.is_element_visible(f"{label_selector}.active") or \
                     self.execute_script(f"return document.querySelector('{label_selector} input').checked")

        if not is_checked:
            self.js_click(label_selector)
            self.wait_for_element_visible(f"{label_selector}.active", timeout=3)

    def click(self, selector, **kwargs):
        self.wait_for_ajax_complete()
        super().click(selector, **kwargs)

    def type(self, selector, text, **kwargs):
        self.wait_for_ajax_complete()
        super().type(selector, text, **kwargs)

    def js_click(self, selector, **kwargs):
        self.wait_for_ajax_complete()
        super().js_click(selector, **kwargs)

    def select_option_by_text(self, selector, option_text, **kwargs):
        self.wait_for_ajax_complete()
        super().select_option_by_text(selector, option_text, **kwargs)


class RecorderTest(CustomBaseCase):
    def test_recording(self):
        # 从配置加载
        cfg = tools.load_config().get("anychat-app", {})
        base_url = cfg.get("base_url", "https://usee-uavp-inner-dev.test.abchina.com.cn/mt/pages")
        username = cfg.get("username", "admin")
        password = cfg.get("password", "Anychat123@")
        apps_str = cfg.get("apps", "")
        apps = [line.strip() for line in apps_str.splitlines() if line.strip()]

        # 登录部分
        self.open(f"{base_url}/login.html")
        self.type("input#fm-login-id", username)
        self.type("input#fm-login-password", password)
        self.click("button#loginserver")
        self.wait_for_text("总览", timeout=10)
        self.click('strong:contains("应用管理")')
        self.click('a[href="javascript:go_url(\'appmgt.html\',3,0)"]')
        self.open_if_not_url(f"{base_url}/appmgt.html")

        # 循环创建应用
        for i, line in enumerate(apps, 1):
            parts = line.strip().split()
            if len(parts) != 2:
                continue
            app_guid, app_name = parts

            # 点击创建按钮
            self.click("h1")
            self.wait_for_element_visible("button#modalstatic", timeout=10)
            self.click("button#modalstatic")

            # 填写应用信息
            self.type("input#appGuid", app_guid)
            self.click("div.div-header")
            self.type("input#AppName", app_name)

            # 确认创建
            self.click('button:contains("确 定")')

            # 点击配置按钮
            self.click("div#appInfo > div:last-child button.setting")

            self.open_if_not_url(f"{base_url}/appdetail.html?appGuid={app_guid}")

            # 配置应用详情
            self.click("button#editbtn4")
            self.wait_for_text("保存", timeout=10)
            self.ensure_checkbox_checked("div#applicationCollapse div:nth-of-type(3) div:nth-of-type(2) label")
            self.ensure_checkbox_checked("div#applicationCollapse div:nth-of-type(4) div:nth-of-type(2) label")
            self.ensure_checkbox_checked("div#applicationCollapse div:nth-of-type(6) div:nth-of-type(2) label")
            self.select_option_by_text("select#ClientAccessEncType", "业务后台验证")
            self.click("button#savebtn4")

            self.click("button#editbtn6")
            self.js_click('label:contains("客户端登录")')
            self.js_click('label:contains("客户端注销")')
            self.js_click('label:contains("进出房间")')
            self.js_click('label:contains("媒体状态事件")')
            self.type("textarea#CallBackURL", "http://localhost:80")
            self.type("textarea#CallBackMD5Pass", "anychat")
            self.click("button#savebtn6")

            # 返回应用列表
            self.wait_for_text("返回", timeout=10)
            self.click('button:contains("返回")')
            self.open_if_not_url(f"{base_url}/appmgt.html")

            print(f"✓ 成功创建第 {i} 个应用: {app_name} (GUID: {app_guid})")
