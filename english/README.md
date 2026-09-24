# 英语学习栏目

入口是门户首页的“英语学习”，地址为 `/english/`。课程使用独立英语密码及 `lumora-english-pass` 会话键；主站登录不会自动解锁英语课程。

`encrypted.html` 是经过加密的完整课程，不是课程编辑源。公开仓库不存放课堂原图、明文课程或密码。补充资料入口仍指向私人英语站，使用原账户访问。

## 更新课程

1. 在私人英语学习库中收集、去重和整理资料，保持单元和题目 ID 稳定。
2. 构建适用于 `/english/` 的完整 HTML，保留返回主页链接。明文文件必须在本仓库之外。
3. 运行 `python3 english_release.py pack /absolute/private/build/index.html`，在隐藏输入框输入英语版块的独立访问密码。不要把密码作为命令行参数或写入文件。
4. 运行 `python3 -m unittest discover -s tests -p 'test_english_release.py'`，检查浏览器中的解锁、课程、自测与返回主页功能，再提交密文产物。
5. 原有 Pages 工作流在每次构建中用 `ENGLISH_PASSWORD` 校验密文并复制到 `docs/english/index.html`。密码不匹配或产物损坏会中止发布，不会输出明文。

若英语密码变更，需使用新密码重新打包此产物。旧私人站与主站是不同域名，复习记录需在旧站导出，再在新站导入；题目 ID 和记录结构保持兼容。

英语登录使用独立会话键 `lumora-english-pass`，不会用主站已保存的密码解锁。修改密码时须同时重打包密文并更新 Actions 的 `ENGLISH_PASSWORD`。
