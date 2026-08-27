# Stitch 本地调用接口

`stitch.sh` 是项目级的 Stitch CLI 桥接脚本；它不包含、读取或提交任何密钥。密钥仅应留在本机环境配置中。

示例：

```bash
./tools/stitch.sh tool list --output json
./tools/stitch.sh tool list_projects --data '{}' --output json
```

本次已创建的私有 Stitch 项目为“浦发能源金融洞察平台｜首页”。当前服务端可创建和读取项目，但 `generate_screen_from_text` 对该账户的默认项目形态返回参数校验错误；Vue 首页因此按已提交的设计说明实现，待该端点可用后可继续使用 `get_screen_code` 导入生成稿。
