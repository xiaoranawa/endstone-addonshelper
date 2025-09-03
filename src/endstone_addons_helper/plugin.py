import os
import shutil
import zipfile
import json
from pathlib import Path
from typing import List, Dict, Optional

from endstone.plugin import Plugin
from endstone.command import Command, CommandSender


class AddonsHelperPlugin(Plugin):
    api_version = "0.10"
    
    commands = {
        "addonlist": {
            "description": "查看已安装的addon",
            "usages": ["/addonlist"],
            "permissions": ["addons_helper.command.addonlist"],
        },
        "packlist": {
            "description": "查看已安装的pack", 
            "usages": ["/packlist"],
            "permissions": ["addons_helper.command.packlist"],
        },
        "deleaddon": {
            "description": "删除指定序号的addon",
            "usages": ["/deleaddon <index: int>"],
            "permissions": ["addons_helper.command.deleaddon"],
        },
        "delepack": {
            "description": "删除指定序号的pack",
            "usages": ["/delepack <index: int>"],
            "permissions": ["addons_helper.command.delepack"],
        },
        "reloadpacks": {
            "description": "重新载入addonshelper文件夹中的mcpack和mcaddon包",
            "usages": ["/reloadpacks"],
            "permissions": ["addons_helper.command.reloadpacks"],
        }
    }
    
    permissions = {
        "addons_helper.command.addonlist": {
            "description": "允许玩家使用 /addonlist 命令",
            "default": True,
        },
        "addons_helper.command.packlist": {
            "description": "允许玩家使用 /packlist 命令", 
            "default": True,
        },
        "addons_helper.command.deleaddon": {
            "description": "允许玩家使用 /deleaddon 命令",
            "default": "op",
        },
        "addons_helper.command.delepack": {
            "description": "允许玩家使用 /delepack 命令",
            "default": "op",
        },
        "addons_helper.command.reloadpacks": {
            "description": "允许玩家使用 /reloadpacks 命令",
            "default": "op",
        }
    }
    
    def on_enable(self):
        """插件启用时调用"""
        self.logger.info("AddonsHelper插件已启用")
        
        #获取目录
        self.server_dir = Path.cwd()
        self.addons_helper_dir = self.server_dir / "plugins" / "addonshelper"
        self.cache_dir = self.addons_helper_dir / ".cache"
        self.enable_json_path = self.cache_dir / "enable.json"
        
        #创建目录
        self.addons_helper_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"已创建addonshelper目录: {self.addons_helper_dir}")
        
        #获取世界名称
        self.world_name = self.get_world_name()
        self.logger.info(f"检测到世界名称: {self.world_name}")
        
        #初始化或加载已安装包记录
        self.load_enable_json()
        
        #处理已存在的addon和资源包文件
        self.process_addon_files()
    
    def on_disable(self):
        """插件禁用时调用"""
        self.logger.info("AddonsHelper插件已禁用")
    
    def get_world_name(self) -> str:
        """从server.properties获取世界名称"""
        try:
            server_props_path = self.server_dir / "server.properties"
            if server_props_path.exists():
                with open(server_props_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('level-name='):
                            world_name = line.split('=', 1)[1].strip()
                            if world_name:
                                return world_name
        except Exception as e:
            self.logger.error(f"读取server.properties失败: {str(e)}")
        
        #获取失败时所使用的默认世界名称，也是基岩版默认的
        return "Bedrock level"
    
    def load_enable_json(self):
        """加载已安装包记录"""
        try:
            if self.enable_json_path.exists():
                with open(self.enable_json_path, 'r', encoding='utf-8') as f:
                    self.enabled_packs = json.load(f)
            else:
                self.enabled_packs = {"addons": [], "packs": []}
        except Exception as e:
            self.logger.error(f"加载enable.json失败: {str(e)}")
            self.enabled_packs = {"addons": [], "packs": []}
    
    def save_enable_json(self):
        """保存已安装包记录"""
        try:
            #清理数据中的无效字符
            cleaned_data = self.clean_json_data(self.enabled_packs)
            
            with open(self.enable_json_path, 'w', encoding='utf-8') as f:
                json.dump(cleaned_data, f, indent=2, ensure_ascii=True)
        except Exception as e:
            self.logger.error(f"保存enable.json失败: {str(e)}")
    
    def clean_json_data(self, data):
        """清理数据中的无效Unicode字符"""
        if isinstance(data, dict):
            return {key: self.clean_json_data(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self.clean_json_data(item) for item in data]
        elif isinstance(data, str):
            #移除代理对字符
            try:
                return data.encode('utf-8', errors='ignore').decode('utf-8')
            except:
                return str(data).encode('ascii', errors='replace').decode('ascii')
        else:
            return data

    def clean_string(self, text: str) -> str:
        """清理字符串中的无效字符"""
        try:
            #移除代理对字符和其他问题字符
            cleaned = text.encode('utf-8', errors='ignore').decode('utf-8')
            return cleaned
        except:
            return str(text).encode('ascii', errors='replace').decode('ascii')
    
    def on_command(self, sender: CommandSender, command: Command, args: List[str]) -> bool:
        """处理命令"""
        if command.name == "addonlist":
            return self.handle_addon_list(sender, command, args)
        elif command.name == "packlist":
            return self.handle_pack_list(sender, command, args)
        elif command.name == "deleaddon":
            return self.handle_dele_addon(sender, command, args)
        elif command.name == "delepack":
            return self.handle_dele_pack(sender, command, args)
        elif command.name == "reloadpacks":
            return self.handle_reload_packs(sender, command, args)
        return True
    
    def handle_addon_list(self, sender: CommandSender, command: Command, args: List[str]) -> bool:
        """处理/addonlist命令"""
        if not self.enabled_packs["addons"]:
            sender.send_message("§c当前没有安装任何addon")
        else:
            sender.send_message("§a已安装的addon:")
            for i, addon in enumerate(self.enabled_packs["addons"], 1):
                sender.send_message(f"§e{i}. {addon['name']}")
        return True
    
    def handle_pack_list(self, sender: CommandSender, command: Command, args: List[str]) -> bool:
        """处理/packlist命令"""
        if not self.enabled_packs["packs"]:
            sender.send_message("§c当前没有安装任何pack")
        else:
            sender.send_message("§a已安装的pack:")
            for i, pack in enumerate(self.enabled_packs["packs"], 1):
                sender.send_message(f"§e{i}. {pack['name']}")
        return True
    
    def handle_dele_addon(self, sender: CommandSender, command: Command, args: List[str]) -> bool:
        """处理/deleaddon命令"""
        if not args:
            sender.send_message("§c请指定要删除的addon序号")
            return True
        
        try:
            index = int(args[0]) - 1
            if 0 <= index < len(self.enabled_packs["addons"]):
                addon = self.enabled_packs["addons"][index]
                self.remove_addon(addon)
                sender.send_message(f"§a成功删除addon: {addon['name']}")
            else:
                sender.send_message("§c序号无效")
        except ValueError:
            sender.send_message("§c请输入有效的数字序号")
        
        return True
    
    def handle_dele_pack(self, sender: CommandSender, command: Command, args: List[str]) -> bool:
        """处理/delepack命令"""
        if not args:
            sender.send_message("§c请指定要删除的pack序号")
            return True
        
        try:
            index = int(args[0]) - 1
            if 0 <= index < len(self.enabled_packs["packs"]):
                pack = self.enabled_packs["packs"][index]
                self.remove_pack(pack)
                sender.send_message(f"§a成功删除pack: {pack['name']}")
            else:
                sender.send_message("§c序号无效")
        except ValueError:
            sender.send_message("§c请输入有效的数字序号")
        
        return True
    
    def handle_reload_packs(self, sender: CommandSender, command: Command, args: List[str]) -> bool:
        """处理/reloadpacks命令"""
        try:
            sender.send_message("§a开始重新载入包文件...")
            
            #重新处理addon和资源包文件
            self.process_addon_files()
            
            sender.send_message("§a包文件重载完成！请重启服务器以使更改生效！")
            self.logger.info("手动触发包文件重载完成")
            
        except Exception as e:
            sender.send_message("§c重载失败，请检查日志")
            self.logger.error(f"手动重载包文件失败: {str(e)}")
        
        return True
    
    def remove_addon(self, addon):
        """删除addon"""
        try:
            #删除文件夹
            if "behavior_folder" in addon:
                behavior_path = self.server_dir / "behavior_packs" / addon["behavior_folder"]
                if behavior_path.exists():
                    shutil.rmtree(behavior_path)
                    self.logger.info(f"已删除行为包文件夹: {addon['behavior_folder']}")
                
                #从世界配置中移除
                self.deactivate_behavior_pack(addon["behavior_uuid"])
            
            if "resource_folder" in addon:
                resource_path = self.server_dir / "resource_packs" / addon["resource_folder"]
                if resource_path.exists():
                    shutil.rmtree(resource_path)
                    self.logger.info(f"已删除资源包文件夹: {addon['resource_folder']}")
                
                #从世界配置中移除
                self.deactivate_resource_pack(addon["resource_uuid"])
            
            #从记录中移除
            self.enabled_packs["addons"].remove(addon)
            self.save_enable_json()
            
        except Exception as e:
            self.logger.error(f"删除addon失败: {str(e)}")
    
    def remove_pack(self, pack):
        """删除pack"""
        try:
            #删除文件夹
            if pack["type"] == "behavior":
                pack_path = self.server_dir / "behavior_packs" / pack["folder"]
                if pack_path.exists():
                    shutil.rmtree(pack_path)
                    self.logger.info(f"已删除行为包文件夹: {pack['folder']}")
                
                #从世界配置中移除
                self.deactivate_behavior_pack(pack["uuid"])
            
            elif pack["type"] == "resource":
                pack_path = self.server_dir / "resource_packs" / pack["folder"]
                if pack_path.exists():
                    shutil.rmtree(pack_path)
                    self.logger.info(f"已删除资源包文件夹: {pack['folder']}")
                
                #从世界配置中移除
                self.deactivate_resource_pack(pack["uuid"])
            
            #从记录中移除
            self.enabled_packs["packs"].remove(pack)
            self.save_enable_json()
            
        except Exception as e:
            self.logger.error(f"删除pack失败: {str(e)}")
    
    def deactivate_behavior_pack(self, pack_uuid: str):
        """从世界配置中移除行为包"""
        try:
            world_behavior_packs_path = self.server_dir / "worlds" / self.world_name / "world_behavior_packs.json"
            if world_behavior_packs_path.exists():
                with open(world_behavior_packs_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                #移除对应的包
                config = [pack for pack in config if pack.get("pack_id") != pack_uuid]
                
                with open(world_behavior_packs_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                
                self.logger.info("已从world_behavior_packs.json中移除包")
        except Exception as e:
            self.logger.error(f"移除行为包配置失败: {str(e)}")
    
    def deactivate_resource_pack(self, pack_uuid: str):
        """从世界配置中移除资源包"""
        try:
            world_resource_packs_path = self.server_dir / "worlds" / self.world_name / "world_resource_packs.json"
            if world_resource_packs_path.exists():
                with open(world_resource_packs_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                #移除对应的包
                config = [pack for pack in config if pack.get("pack_id") != pack_uuid]
                
                with open(world_resource_packs_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                
                self.logger.info("已从world_resource_packs.json中移除包")
        except Exception as e:
            self.logger.error(f"移除资源包配置失败: {str(e)}")
    
    def process_addon_files(self):
        """处理addonshelper目录中的mcaddon和mcpack文件"""
        if not self.addons_helper_dir.exists():
            return
        
        #查找mcaddon和mcpack文件
        mcaddon_files = list(self.addons_helper_dir.glob("*.mcaddon"))
        mcpack_files = list(self.addons_helper_dir.glob("*.mcpack"))
        
        if not mcaddon_files and not mcpack_files:
            return
        
        self.logger.info(f"发现 {len(mcaddon_files)} 个mcaddon文件和 {len(mcpack_files)} 个mcpack文件")
        
        #处理mcaddon文件
        for mcaddon_file in mcaddon_files:
            self.process_mcaddon(mcaddon_file)
        
        #处理mcpack文件
        for mcpack_file in mcpack_files:
            self.process_mcpack(mcpack_file)

        if mcaddon_files or mcpack_files:
            self.logger.warning("包安装完成！请重启服务器以使更改生效！")
    
    def process_mcaddon(self, mcaddon_path: Path):
        """处理mcaddon文件"""
        try:
            self.logger.info(f"正在处理mcaddon文件")
            
            #解压mcaddon文件到临时目录
            temp_dir = self.addons_helper_dir / "temp" / mcaddon_path.stem
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            with zipfile.ZipFile(mcaddon_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            #创建addon记录
            addon_record = {
                "name": mcaddon_path.stem,
                "type": "addon"
            }
            
            #处理解压后的内容
            behavior_pack_dir = self.server_dir / "behavior_packs"
            resource_pack_dir = self.server_dir / "resource_packs"
            
            behavior_pack_dir.mkdir(exist_ok=True)
            resource_pack_dir.mkdir(exist_ok=True)
            
            #遍历解压的内容
            for item in temp_dir.iterdir():
                if item.is_dir():
                    manifest_path = item / "manifest.json"
                    if manifest_path.exists():
                        pack_info = self.read_manifest(manifest_path)
                        if pack_info:
                            pack_type = pack_info.get("type")
                            pack_name = self.clean_string(pack_info.get("name", item.name))
                            pack_uuid = pack_info.get("uuid", "")
                            pack_version = pack_info.get("version", [1, 0, 0])
                            
                            if pack_type == "data":  # 行为包
                                target_dir = behavior_pack_dir / item.name
                                shutil.copytree(item, target_dir, dirs_exist_ok=True)
                                
                                # 激活行为包
                                self.activate_behavior_pack(pack_uuid, pack_version)
                                
                                # 记录到addon
                                addon_record["behavior_folder"] = item.name
                                addon_record["behavior_uuid"] = pack_uuid
                                addon_record["name"] = pack_name
                                
                                self.logger.info(f"已安装并激活行为包: {pack_name}")
                            
                            elif pack_type == "resources":  # 资源包
                                target_dir = resource_pack_dir / item.name
                                shutil.copytree(item, target_dir, dirs_exist_ok=True)
                                
                                # 激活资源包
                                self.activate_resource_pack(pack_uuid, pack_version)
                                
                                # 记录到addon
                                addon_record["resource_folder"] = item.name
                                addon_record["resource_uuid"] = pack_uuid
                                if "name" not in addon_record:
                                    addon_record["name"] = pack_name
                                
                                self.logger.info(f"已安装并激活资源包: {pack_name}")
            
            # 保存addon记录
            self.enabled_packs["addons"].append(addon_record)
            self.save_enable_json()
            
            # 清理临时文件
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            # 删除原mcaddon文件
            mcaddon_path.unlink()
            self.logger.info(f"已删除原mcaddon文件")
            
        except Exception as e:
            self.logger.error(f"处理mcaddon文件时出错: {str(e)}")
    
    def process_mcpack(self, mcpack_path: Path):
        """处理mcpack文件"""
        try:
            self.logger.info(f"正在处理mcpack文件")
            
            # 解压mcpack文件到临时目录
            temp_dir = self.addons_helper_dir / "temp" / mcpack_path.stem
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            with zipfile.ZipFile(mcpack_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # 读取manifest.json确定包类型
            manifest_path = temp_dir / "manifest.json"
            if manifest_path.exists():
                pack_info = self.read_manifest(manifest_path)
                if pack_info:
                    pack_type = pack_info.get("type")
                    pack_name = self.clean_string(pack_info.get("name", mcpack_path.stem))
                    pack_uuid = pack_info.get("uuid", "")
                    pack_version = pack_info.get("version", [1, 0, 0])
                    
                    pack_record = {
                        "name": pack_name,
                        "folder": mcpack_path.stem,
                        "uuid": pack_uuid,
                        "type": ""
                    }
                    
                    if pack_type == "data":  # 行为包
                        target_dir = self.server_dir / "behavior_packs" / mcpack_path.stem
                        self.server_dir.joinpath("behavior_packs").mkdir(exist_ok=True)
                        shutil.copytree(temp_dir, target_dir, dirs_exist_ok=True)
                        
                        # 激活行为包
                        self.activate_behavior_pack(pack_uuid, pack_version)
                        pack_record["type"] = "behavior"
                        
                        self.logger.info(f"已安装并激活行为包: {pack_name}")
                    
                    elif pack_type == "resources":  # 资源包
                        target_dir = self.server_dir / "resource_packs" / mcpack_path.stem
                        self.server_dir.joinpath("resource_packs").mkdir(exist_ok=True)
                        shutil.copytree(temp_dir, target_dir, dirs_exist_ok=True)
                        
                        # 激活资源包
                        self.activate_resource_pack(pack_uuid, pack_version)
                        pack_record["type"] = "resource"
                        
                        self.logger.info(f"已安装并激活资源包: {pack_name}")
                    
                    # 保存记录
                    self.enabled_packs["packs"].append(pack_record)
                    self.save_enable_json()
            
            # 清理临时文件
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            # 删除原mcpack文件
            mcpack_path.unlink()
            self.logger.info(f"已删除原mcpack文件")
            
        except Exception as e:
            self.logger.error(f"处理mcpack文件时出错: {str(e)}")
    
    def activate_behavior_pack(self, pack_uuid: str, pack_version: list):
        """激活行为包"""
        try:
            world_behavior_packs_path = self.server_dir / "worlds" / self.world_name / "world_behavior_packs.json"
            
            # 确保目录存在
            world_behavior_packs_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 读取现有配置
            if world_behavior_packs_path.exists():
                with open(world_behavior_packs_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = []
            
            # 检查是否已经存在
            pack_entry = {
                "pack_id": pack_uuid,
                "version": pack_version
            }
            
            if not any(pack.get("pack_id") == pack_uuid for pack in config):
                config.append(pack_entry)
                
                # 写回文件
                with open(world_behavior_packs_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                
                self.logger.info("已更新world_behavior_packs.json")
        except Exception as e:
            self.logger.error(f"激活行为包失败: {str(e)}")
    
    def activate_resource_pack(self, pack_uuid: str, pack_version: list):
        """激活资源包"""
        try:
            world_resource_packs_path = self.server_dir / "worlds" / self.world_name / "world_resource_packs.json"
            
            # 确保目录存在
            world_resource_packs_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 读取现有配置
            if world_resource_packs_path.exists():
                with open(world_resource_packs_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = []
            
            # 检查是否已经存在
            pack_entry = {
                "pack_id": pack_uuid,
                "version": pack_version
            }
            
            if not any(pack.get("pack_id") == pack_uuid for pack in config):
                config.append(pack_entry)
                
                # 写回文件
                with open(world_resource_packs_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                
                self.logger.info("已更新world_resource_packs.json")
        except Exception as e:
            self.logger.error(f"激活资源包失败: {str(e)}")
    
    def read_manifest(self, manifest_path: Path) -> Dict:
        """读取manifest.json文件"""
        try:
            with open(manifest_path, 'r', encoding='utf-8-sig') as f:
                manifest = json.load(f)
            
            header = manifest.get('header', {})
            modules = manifest.get('modules', [{}])
            module_type = modules[0].get('type', 'unknown') if modules else 'unknown'
            
            return {
                'name': header.get('name', ''),
                'description': header.get('description', ''),
                'uuid': header.get('uuid', ''),
                'version': header.get('version', [1, 0, 0]),
                'type': module_type
            }
        except UnicodeDecodeError:
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content.startswith('\ufeff'):
                        content = content[1:]
                    manifest = json.loads(content)
                
                header = manifest.get('header', {})
                modules = manifest.get('modules', [{}])
                module_type = modules[0].get('type', 'unknown') if modules else 'unknown'
                
                return {
                    'name': header.get('name', ''),
                    'description': header.get('description', ''),
                    'uuid': header.get('uuid', ''),
                    'version': header.get('version', [1, 0, 0]),
                    'type': module_type
                }
            except Exception as e:
                self.logger.error(f"读取manifest.json失败（第二次尝试）: {str(e)}")
                return {}
        except Exception as e:
            self.logger.error(f"读取manifest.json失败: {str(e)}")
            return {}
