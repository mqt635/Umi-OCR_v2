# ===============================================
# =============== 命令行-解析和执行 ===============
# ===============================================

import time
import argparse
from ..utils.call_func import CallFunc


# 命令执行器
class _Actuator:
    def __init__(self):
        self.pyDict = {}  # python模块字典
        self.qmlDict = {}  # qml模块字典
        self.tagPageConn = None  # 页面连接器的引用

    # 初始化，并收集信息。传入qml模块字典
    def initCollect(self, qmlModuleDict):
        qmlModuleDict = qmlModuleDict.toVariant()
        self.qmlDict.update(qmlModuleDict)
        # 获取页面连接器实例
        from ..tag_pages.tag_pages_connector import TagPageConnObj

        self.tagPageConn = TagPageConnObj

    # ============================== 页面管理 ==============================

    # 返回当前 [可创建的页面模板] 和 [已创建的页面] 的信息
    def getAllPages(self):
        TabViewManager = self.qmlDict["TabViewManager"]
        pageList = TabViewManager.getPageList().toVariant()
        infoStr = "All opened pages:\npage_index\tkey\ttitle\n"
        for index, value in enumerate(pageList):
            infoStr += f'{index}\t{value["ctrlKey"]}\t{value["info"]["title"]}\n'

        infoList = TabViewManager.getInfoList().toVariant()
        infoStr += (
            "\nAll page templates that can be opened:\ntemplate_index\tkey\ttitle\n"
        )
        for index, value in enumerate(infoList):
            infoStr += f'{index}\t{value["key"]}\t{value["title"]}\n'

        infoStr += "\nUsage of create a page:\n"
        infoStr += "    Umi-OCR --add_page [template_index]\n"
        infoStr += "Usage of delete a page:\n"
        infoStr += "    Umi-OCR --del_page [page_index]\n"
        infoStr += "Usage of query the modules that can be called:\n"
        infoStr += "    Umi-OCR --all_modules\n"

        return infoStr

    # 创建页面
    def addPage(self, index):
        try:
            index = int(index)
        except ValueError:
            return f"[Error] template_index must be integer, not {index}."
        TabViewManager = self.qmlDict["TabViewManager"]
        infoList = TabViewManager.getInfoList().toVariant()
        l = len(infoList) - 1
        if index < 0 or index > l:
            return f"[Error] template_index {index} out of range (0~{l})."
        return self.call("TabViewManager", "qml", "addTabPage", False, -1, index)

    # 删除页面
    def delPage(self, index):
        try:
            index = int(index)
        except ValueError:
            return f"[Error] page_index must be integer, not {index}."
        TabViewManager = self.qmlDict["TabViewManager"]
        pageList = TabViewManager.getPageList().toVariant()
        l = len(pageList) - 1
        if index < 0 or index > l:
            return f"[Error] page_index {index} out of range (0~{l})."
        return self.call("TabViewManager", "qml", "delTabPage", False, index)

    # ============================== 动态模块调用 ==============================

    # 返回所有可调用模块
    def getModules(self):
        pyd, qmld = {}, {}
        pages = self.tagPageConn.pages
        for p in pages:
            if pages[p]["qmlObj"]:
                qmld[p] = pages[p]["qmlObj"]
            if pages[p]["pyObj"]:
                pyd[p] = pages[p]["pyObj"]
        pyd.update(self.pyDict)
        qmld.update(self.qmlDict)
        return {"py": pyd, "qml": qmld}

    # 传入(不完整的)模块名，搜索并返回模块实例。type: py / qml
    def getModuleFromName(self, moduleName, type_):
        d = self.getModules()[type_]
        module = None
        if moduleName in d:
            module = d[moduleName]
        else:
            for name in d.keys():  # 若输入模块名的前几个字母，也可以匹配
                if name.startswith(moduleName):
                    moduleName = name
                    module = d[name]
                    break
        return module, moduleName

    # 返回所有可调用模块的帮助信息
    def getModulesHelp(self):
        modules = self.getModules()
        help = "\nPython modules: (Usage: Umi-OCR --call_py [module name])\n"
        for k in modules["py"].keys():
            help += f"    {k}\n"
        help += "\nQml modules: (Usage: Umi-OCR --call_qml [module name])\n"
        for k in modules["qml"].keys():
            help += f"    {k}\n"
        help += f"\nTips: module name can only write the first letters, such as [ScreenshotOCR_1] → [Scr]"
        return help

    # 返回一个模块的所有函数的帮助信息
    def getModuleFuncsHelp(self, moduleName, type_):
        module, moduleName = self.getModuleFromName(moduleName, type_)
        typeStr = "Python" if type_ == "py" else "qml"
        if not module:
            return f'[Error] {typeStr} module "{moduleName}" non-existent.'
        funcs = [
            func
            for func in vars(type(module)).keys()
            if callable(getattr(module, func))
        ]
        help = f'All functions in {typeStr} module "{moduleName}":\n'
        for f in funcs:
            f = str(f)
            if not f.startswith("_"):
                help += f"    {f}\n"
        help += f"Usage: Umi-OCR --call_qml {moduleName} --func [function name]\n"
        return help

    # 调用一个模块函数。type: py / qml , thread: True 同步在子线程 / False 异步在主线程
    def call(self, moduleName, type_, funcName, thread, *paras):
        module, moduleName = self.getModuleFromName(moduleName, type_)
        typeStr = "Python" if type_ == "py" else "qml"
        if not module:
            return f'[Error] {typeStr} module "{moduleName}" non-existent.'
        func = getattr(module, funcName, None)
        if not func:
            return f'[Error] func "{funcName}" not exist in {typeStr} module "{moduleName}".'
        try:
            if thread:  # 在子线程执行，返回结果
                return func(*paras)
            else:  # 在主线程执行，返回标志文本
                CallFunc.now(func, *paras)  # 在主线程中调用回调函数
                return f'Calling "{funcName}" in main thread.'
        except Exception as e:
            return f'[Error] calling {typeStr} module "{moduleName}" - "{funcName}" {paras}: {e}'

    # ============================== 便捷指令 ==============================

    # 控制主窗口
    def ctrlWindow(self, show, hide, quit):
        if show:
            self.call("MainWindow", "qml", "setVisibility", False, True)
            return "Umi-OCR show."
        elif hide:
            self.call("MainWindow", "qml", "setVisibility", False, False)
            return "Umi-OCR hide."
        elif quit:
            self.call("MainWindow", "qml", "quit", False)
            return "Umi-OCR quit."

    # 截图或粘贴，并获取返回结果
    def screenshot_clipboard(self, ss, clip):
        # 检查截图标签页，如果未创建则创建
        module, moduleName = self.getModuleFromName("ScreenshotOCR", "py")
        if module == None:
            tvm = self.qmlDict["TabViewManager"]
            infoList = tvm.getInfoList().toVariant()
            f2 = False
            for i, v in enumerate(infoList):
                if v["key"] == "ScreenshotOCR":
                    f2 = True
                    self.addPage(i)
                    break
            if not f2:
                return '[Error] Template "ScreenshotOCR" not found.'
            for i in range(10):
                time.sleep(0.5)
                module, moduleName = self.getModuleFromName("ScreenshotOCR", "py")
                if not module == None:
                    break
        if module == None:
            return '[Error] Unable to create template "ScreenshotOCR".'
        # 调用截图标签页的函数
        if ss:
            self.call(moduleName, "qml", "screenshot", False)
        elif clip:
            self.call(moduleName, "qml", "paste", False)
        # 等待OCR完成
        for i in range(60):
            time.sleep(0.5)
            res = self.call(moduleName, "py", "getRecentResult", True)
            if res:
                if res["code"] == 100:
                    text = ""
                    for r in res["data"]:
                        text += r["text"] + "\n"
                    return text
                elif res["code"] == 101:
                    return "[Message] No text in OCR result."
                elif res["code"] == 102:
                    return res["data"]
                else:
                    return f'[Error] Code: {res["code"]}\nMessage: {res["data"]}.'
        return "[Error] OCR waiting timeout."


CmdActuator = _Actuator()


# 命令解析器
class _Cmd:
    def __init__(self):
        self._parser = None

    def init(self):
        if self._parser:
            return
        self._parser = argparse.ArgumentParser(prog="Umi-OCR")
        # 便捷指令
        self._parser.add_argument(
            "--show", action="store_true", help="Make the app appear in the foreground."
        )
        self._parser.add_argument(
            "--hide", action="store_true", help="Hide app in the background."
        )
        self._parser.add_argument("--quit", action="store_true", help="Quit app.")
        self._parser.add_argument(
            "--screenshot",
            action="store_true",
            help="Screenshot OCR and output the result.",
        )
        self._parser.add_argument(
            "--clipboard",
            action="store_true",
            help="Clipboard OCR and output the result.",
        )
        # 页面管理
        self._parser.add_argument(
            "--all_pages",
            action="store_true",
            help="Output all template and page information.",
        )
        self._parser.add_argument(
            "--add_page", type=int, help="usage: Umi-OCR --all_pages"
        )
        self._parser.add_argument(
            "--del_page", type=int, help="usage: Umi-OCR --all_pages"
        )
        # 函数调用
        self._parser.add_argument(
            "--all_modules",
            action="store_true",
            help="Output all module names that can be called.",
        )
        self._parser.add_argument(
            "--call_py", help="Calling a function on a Python module."
        )
        self._parser.add_argument(
            "--call_qml", help="Calling a function on a Qml module."
        )
        self._parser.add_argument(
            "--func", help="The name of the function to be called."
        )
        self._parser.add_argument(
            "--thread",
            action="store_true",
            help="The function will be called on the child thread and return the result, but it may be unstable or cause QML to crash.",
        )
        self._parser.add_argument("paras", nargs="*", help="parameters of [--func].")

    # 分析指令，返回指令对象或报错字符串
    def parse(self, argv):
        self.init()
        # 特殊情况
        if "-h" in argv or "--help" in argv:  # 帮助
            return self._parser.format_help()
        if len(argv) == 0:  # 空指令
            CmdActuator.ctrlWindow(True, False, False)  # 展示主窗
            return self._parser.format_help()  # 返回帮助
        # 正常解析
        try:
            return self._parser.parse_args(argv)
        except SystemExit as e:
            return f"Your argv: {argv}\n[Error]: {e}\nusage: Umi-OCR --help"
        except Exception as e:
            return f"Your argv: {argv}\n[Error]: {e}\nusage: Umi-OCR --help"

    # 执行指令，返回执行结果字符串
    def execute(self, argv):
        args = self.parse(argv)
        if type(args) == str:
            return args
        if args.all_modules:
            return CmdActuator.getModulesHelp()
        # 便捷指令
        if args.show or args.hide or args.quit:  # 控制主窗
            return CmdActuator.ctrlWindow(args.show, args.hide, args.quit)
        if args.screenshot or args.clipboard:  # 截图或粘贴
            return CmdActuator.screenshot_clipboard(args.screenshot, args.clipboard)
        # 页面管理
        if args.all_pages:
            return CmdActuator.getAllPages()
        if not args.add_page is None:
            return CmdActuator.addPage(args.add_page)
        if not args.del_page is None:
            return CmdActuator.delPage(args.del_page)
        # 动态模块调用
        if args.call_py:
            if args.func:
                return CmdActuator.call(
                    args.call_py, "py", args.func, args.thread, *args.paras
                )
            else:
                return CmdActuator.getModuleFuncsHelp(args.call_py, "py")
        if args.call_qml:
            if args.func:
                return CmdActuator.call(
                    args.call_qml, "qml", args.func, args.thread, *args.paras
                )
            else:
                return CmdActuator.getModuleFuncsHelp(args.call_qml, "qml")


CmdServer = _Cmd()
