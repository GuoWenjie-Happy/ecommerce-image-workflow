# 电商流程文件工具

固定入口：`ecom_files.py`。依赖 Python 3 与 Pillow；先检查现有运行环境，已有依赖不要重复安装。缺依赖时使用 `python -m pip install -r requirements.txt`。

所有输出拒绝覆盖既有文件；修改版本需新文件名。输入文件不会改写。脚本不生图、不抠图、不改标签、不换瓶、不修复背景，不给出视觉通过结论。

```powershell
# 查看实际尺寸、比例、透明通道、近白边缘采样与近似主体占比
python ecom_files.py inspect "产品素材目录" --report "工作目录\素材检查.json"

# 主图正方形等比导出1000宽；非方图拒绝拉伸或裁切
python ecom_files.py export "原件.png" "交付\主图\01.png" --width 1000 --square

# 详情保留实际比例，等比导出900宽；上采样会标明
python ecom_files.py export "详情原件.png" "交付\详情\01.png" --width 900

# 仅从通过项目录制作两类预览；输出放在图片目录之外
python ecom_files.py preview main "交付\主图" "交付\主图预览.jpg" --width 400 --columns 3
python ecom_files.py preview detail "交付\详情" "交付\详情图预览.jpg" --width 400

# 参考与交付文件均用相同编号作文件名，如01.png、02.jpg
python ecom_files.py count "参考\详情" "交付\详情" --report "工作目录\数量核对.json"
```

详情预览按数字文件名顺序等宽、从上到下拼接，不拉伸或裁切。主图联系表保留完整图片。极长JPEG不支持时脚本报错，可以明确使用PNG或降低预览宽度，不能假称生成成功。

主体占比是背景阈值或alpha边框的近似测量，可能包含阴影，须人工核对；不应用其修正产品轮廓。检查白底时仅报告结果，不能据此宣称完整背景都为纯白。数量核对不检查文案或SKU，仍需审核。

每轮复用本脚本，命令参数指定本轮独立目录；不要复制到每个产品后各自改写。确有缺失功能时在本目录维护通用功能，不编写替代视觉制作的临时脚本。
