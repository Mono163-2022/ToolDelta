import os
import platform
import shutil
import shlex
import json
import time
from tooldelta.builtins import Builtins
from tooldelta.color_print import Print
from tooldelta.plugin_market import market
from tooldelta.plugin_load import PluginRegData
from tooldelta.constants import (
    TOOLDELTA_PLUGIN_DIR,
    TOOLDELTA_CLASSIC_PLUGIN,
    TOOLDELTA_INJECTED_PLUGIN
)

JsonIO = Builtins.SimpleJsonDataReader

if platform.system().lower() == "windows":
    CLS_CMD = "cls"
else:
    CLS_CMD = "clear"

clear_screen = lambda: os.system(shlex.quote(CLS_CMD))

class PluginManager:
    plugin_reg_data_path = "插件注册表"
    default_reg_data = {"classic": {}, "injected": {}, "unknown": {}}
    _plugin_datas_cache = []

    def manage_plugins(self):
        # 进入插件管理界面
        clear_screen()
        np = self.register_plugins_auto()
        if np > 0:
            Print.clean_print(f"§a已自动注册{np}个未被注册的插件.")
        while 1:
            plugins = self.list_plugins_list()
            Print.clean_print("§f输入§bu§f更新本地所有插件, §f输入§cq§f退出")
            Print.clean_print("§f输入§ds§f同步插件注册表信息(在手动安装插件后使用)")
            r = input(Print.clean_fmt("§f输入插件关键词进行选择\n(空格可分隔关键词):"))
            r1 = r.strip().lower()
            if r1 == "":
                continue
            elif r1 == "s":
                self.sync_plugin_datas_to_register()
                Print.clean_print("§a同步插件注册表数据成功.")
                time.sleep(2)
            elif r1 == "q":
                return
            elif r1 == "u":
                self.update_all_plugins(
                    self.get_plugin_reg_name_dict_and_datas()[1]
                )
            else:
                res = self.search_plugin(r, plugins)
                if res is None:
                    input()
                else:
                    self.plugin_operation(res)
            clear_screen()

    def plugin_operation(self, plugin: PluginRegData):
        # 对插件进行操作
        description_fixed = plugin.description.replace('\n', '\n    ')
        clear_screen()
        Print.clean_print(f"§d插件名: §f{plugin.name}")
        Print.clean_print(f" - 版本: {plugin.version_str}")
        Print.clean_print(f" - 作者: {plugin.author}")
        Print.clean_print(f" 描述: {description_fixed}")
        Print.clean_print(f"§f1.删除插件  2.检查更新  3.{'禁用插件' if plugin.is_enabled else '启用插件'}")
        f_dirname = {
            "classic": TOOLDELTA_CLASSIC_PLUGIN,
            "injected": TOOLDELTA_INJECTED_PLUGIN
        }[plugin.plugin_type]
        match input(Print.clean_fmt("§f请选择选项: ")):
            case "1":
                r = input(
                    Print.clean_fmt("§c删除插件操作不可逆, 请输入y, 其他取消: ")
                ).lower()
                if r != "y":
                    return
                plugin_dir = os.path.join("插件文件", f_dirname, plugin.name)
                shutil.rmtree(
                    plugin_dir + ("+disabled" if not plugin.is_enabled else "")
                )
                Print.clean_print(f"§a已成功删除插件 {plugin.name}, 回车键继续")
                self.pop_plugin_reg_data(plugin)
                input()
                return
            case "2":
                latest_version = market.get_latest_plugin_version(plugin.plugin_id)
                if latest_version is None:
                    Print.clean_print("§6无法获取其的最新版本, 回车键继续")
                elif latest_version == plugin.version_str:
                    Print.clean_print("§a此插件已经为最新版本, 回车键继续")
                else:
                    Print.clean_print(f"§a插件有新版本可用 ({plugin.version_str} => {latest_version})")
                    r = input(Print.clean_fmt("输入§a1§f=立刻更新, §62§f=取消更新: ")).strip()
                    if r == "1":
                        Print.clean_print("§a正在下载新版插件...", end = "\r")
                        market.download_plugin(plugin, market.get_datas_from_market())
                        Print.clean_print("§a插件更新完成, 回车键继续")
                        plugin.version = (int(i) for i in latest_version.split("."))
                    else:
                        Print.clean_print("§6已取消, 回车键返回")
            case "3":
                if plugin.is_enabled:
                    os.rename(
                        os.path.join("插件文件", f_dirname, plugin.name),
                        os.path.join("插件文件", f_dirname, plugin.name + "+disabled")
                    )
                else:
                    os.rename(
                        os.path.join("插件文件", f_dirname, plugin.name + "+disabled"),
                        os.path.join("插件文件", f_dirname, plugin.name)
                    )
                plugin.is_enabled = [True, False][plugin.is_enabled]
                Print.clean_print(f"§6当前插件状态为: {['§c禁用', '§a启用'][plugin.is_enabled]}")
        self.push_plugin_reg_data(plugin)
        input()

    def update_all_plugins(self, plugins: list[PluginRegData]):
        market_datas = market.get_datas_from_market()["MarketPlugins"]
        need_updates: list[tuple[PluginRegData, str]] = []
        for i in plugins:
            s_data = market_datas.get(i.plugin_id)
            if s_data is None:
                continue
            if i.version_str != s_data["version"]:
                need_updates.append((i, s_data["version"]))
        if need_updates:
            clear_screen()
            Print.clean_print("§f以下插件可进行更新:")
            for plugin, v in need_updates:
                Print.clean_print(f" - {plugin.name} §6{plugin.version_str}§f -> §a{v}")
            r = input(Print.clean_fmt("§f输入§a y §f开始更新, §c n §f取消: ")).strip().lower()
            if r == "y":
                for plugin, v in need_updates:
                    market.download_plugin(plugin)
                Print.clean_print("§a全部插件已更新完成")
            else:
                Print.clean_print("§6已取消插件更新.")
            input("[Enter键继续...]")
        else:
            input(Print.clean_fmt("§a无可更新的插件. [Enter键继续]"))

    def search_plugin(self, resp, plugins):
        res = self.search_plugin_by_kw(resp.split(" "), plugins)
        if res == []:
            Print.clean_print("§c没有任何已安装插件匹配得上关键词")
            return None
        if len(res) > 1:
            Print.clean_print("§a☑ §f关键词查找到的插件:")
            for i, plugin in enumerate(res):
                Print.clean_print(str(i + 1) + ". " + self.make_plugin_icon(plugin))
            r = Builtins.try_int(input(Print.clean_fmt("§f请选择序号: ")))
            if r is None or r not in range(1, len(res) + 1):
                Print.clean_print("§c序号无效, 回车键继续")
                return None
            return res[r - 1]
        return res[0]

    @staticmethod
    def search_plugin_by_kw(kws: list[str], plugins: list[PluginRegData]):
        res = []
        for plugin in plugins:
            if all(kw in plugin.name for kw in kws):
                res.append(plugin)
        return res

    def plugin_is_registered(self, plugin_name: str):
        if not self._plugin_datas_cache:
            _, self._plugin_datas_cache = self.get_plugin_reg_name_dict_and_datas()
        for i in self._plugin_datas_cache:
            if i.name == plugin_name:
                return True
        return False

    def register_plugins_auto(self):
        dirs = [TOOLDELTA_CLASSIC_PLUGIN, TOOLDELTA_INJECTED_PLUGIN]
        any_plugin_registered = 0
        for f_dir in dirs:
            dirs_type = {TOOLDELTA_CLASSIC_PLUGIN: "classic", TOOLDELTA_INJECTED_PLUGIN: "injected"}[f_dir]
            for plugin_path in os.listdir(os.path.join(TOOLDELTA_PLUGIN_DIR, f_dir)):
                datpath = os.path.join(TOOLDELTA_PLUGIN_DIR, f_dir, plugin_path, "datas.json")
                if not self.plugin_is_registered(dirs_type) and os.path.isfile(datpath):
                    with open(datpath, "r", encoding="utf-8") as f:
                        jsdata = json.load(f)
                        self.push_plugin_reg_data(PluginRegData(plugin_path, jsdata))
                        any_plugin_registered += 1
        return any_plugin_registered

    def sync_plugin_datas_to_register(self):
        "同步所有插件注册数据至注册表"
        dirs = [TOOLDELTA_CLASSIC_PLUGIN, TOOLDELTA_INJECTED_PLUGIN]
        all_regs = {"classic": {}, "injected": {}}
        sync_num = 0
        for f_dir in dirs:
            dirs_type = {TOOLDELTA_CLASSIC_PLUGIN: "classic", TOOLDELTA_INJECTED_PLUGIN: "injected"}[f_dir]
            for plugin_path in os.listdir(os.path.join(TOOLDELTA_PLUGIN_DIR, f_dir)):
                datpath = os.path.join(TOOLDELTA_PLUGIN_DIR, f_dir, plugin_path, "datas.json")
                if os.path.isfile(datpath):
                    with open(datpath, "r", encoding="utf-8") as f:
                        jsdata = json.load(f)
                        all_regs[dirs_type][plugin_path] = PluginRegData(plugin_path, jsdata).dump()
                        sync_num += 1
        JsonIO.writeFileTo("主系统核心数据", self.plugin_reg_data_path, all_regs)
        return sync_num

    def push_plugin_reg_data(self, plugin_data: PluginRegData):
        # 向插件注册表推送插件注册信息
        r = JsonIO.readFileFrom(
            "主系统核心数据", self.plugin_reg_data_path, self.default_reg_data
        )
        r[plugin_data.plugin_type][plugin_data.name] = plugin_data.dump()
        JsonIO.writeFileTo("主系统核心数据", self.plugin_reg_data_path, r)

    def pop_plugin_reg_data(self, plugin_data: PluginRegData):
        # 从插件注册表删除插件注册信息
        r = JsonIO.readFileFrom("主系统核心数据", self.plugin_reg_data_path)
        del r[plugin_data.plugin_type][plugin_data.name]
        JsonIO.writeFileTo("主系统核心数据", self.plugin_reg_data_path, r)

    def get_plugin_reg_name_dict_and_datas(self):
        # 返回一个表示插件所在类别下的全部已注册插件的列表, 和全部已注册插件的插件注册信息列表
        r0: dict[str, list[str]] = {"classic": [], "injected": []}
        r = JsonIO.readFileFrom(
            "主系统核心数据", self.plugin_reg_data_path, self.default_reg_data
        )
        f_dirname = {
            "classic": TOOLDELTA_CLASSIC_PLUGIN,
            "injected": TOOLDELTA_INJECTED_PLUGIN
        }
        res: list[PluginRegData] = []
        for _, r1 in r.items():
            for k, v in r1.items():
                if not isinstance(k, str) or not isinstance(v, dict):
                    raise ValueError(
                        f"获取插件注册表出现问题: 类型出错: {k.__class__.__name__}, {v.__class__.__name__}"
                    )
                v.update({"name": k})
                p = PluginRegData(k, v)
                if (
                    os.path.exists(os.path.join("插件文件", f_dirname[p.plugin_type], p.name))
                    or os.path.exists(os.path.join("插件文件", f_dirname[p.plugin_type], p.name + "+disabled"))
                ):
                    res.append(p)
                    r0[p.plugin_type].append(p.name)
        return r0, res

    def get_2_compare_plugins_reg(self):
        # 返回一个全注册插件的列表
        f_plugins: list[PluginRegData] = []
        reg_dict, reg_list = self.get_plugin_reg_name_dict_and_datas()
        for p, k in {
            TOOLDELTA_CLASSIC_PLUGIN: "classic",
            TOOLDELTA_INJECTED_PLUGIN: "injected",
        }.items():
            for i in os.listdir(os.path.join("插件文件", p)):
                if i.replace("+disabled", "") not in reg_dict[k]:
                    f_plugins.append(PluginRegData(i, {"plugin-type": k}, False))
        return f_plugins + reg_list
    @staticmethod
    def make_plugin_icon(plugin: PluginRegData):
        ico_colors = { "classic": "§b", "injected": "§d"}
        return (
            ico_colors.get(plugin.plugin_type, "§7")
            + "■ "
            + (("§a"if plugin.is_enabled else "§7") if plugin.is_registered else "§6")
            + plugin.name
        )

    def make_printable_list(self, plugins: list[PluginRegData]):
        texts = []
        for plugin in plugins:
            texts.append(self.make_plugin_icon(plugin))
        lfts = []
        rgts = []
        for i, t in enumerate(texts):
            if (i + 1) % 2 == 1:
                lfts.append(t)
            else:
                rgts.append(t)
        for i, t in enumerate(lfts):
            if i in range(len(rgts)):
                Print.clean_print("§f" + Print.align(t, 35) + "§f" + Print.align(rgts[i]))
            else:
                Print.clean_print("§f" + Print.align(t, 35))

    @staticmethod
    def test_name_same(name: str, dirname: str):
        if name != dirname:
            raise AssertionError(f"插件名: {name} 与文件夹名({dirname}) 不一致") from None

    def list_plugins_list(self):
        Print.clean_print("§a☑ §f目前已安装的插件列表:")
        all_plugins = self.get_2_compare_plugins_reg()
        self.make_printable_list(all_plugins)
        return all_plugins


plugin_manager = PluginManager()
