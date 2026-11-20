from pathlib import Path


root = Path(__file__).resolve().parents[1]

release = (root / 'RELEASE.md').read_text(encoding='utf-8')
for heading in ('## 日常更新', '## 正式发布', '## 版本号选择', '## 发布失败时'):
    assert heading in release, heading
for command in (
    'python tools/verify_package.py --build',
    'git push origin main',
    'git tag -a vX.Y.Z',
    'git push origin vX.Y.Z',
):
    assert command in release, command
assert '日常更新不修改 `VERSION`' in release

agents = (root / 'AGENTS.md').read_text(encoding='utf-8')
readme = (root / 'README.md').read_text(encoding='utf-8')
assert 'RELEASE.md' in agents
assert 'RELEASE.md' in readme

workflow = (root / 'references' / 'workflow.md').read_text(encoding='utf-8')
for category in ('销售主体', '销售包装', '内容物', '随货配件', '拍摄道具', '人物或手部', '环境背景', '未知内容'):
    assert category in workflow, category
assert '未知不等于辅助内容' in workflow
assert '不得进入已验收的白底或透明底素材' in workflow
assert '只阻断依赖该判断的视角或任务' in workflow

for phrase in (
    '生成目标为原生2400×2400px',
    '原件必须保持1:1',
    '实际像素尺寸不是2400×2400px不作为返修或重出理由',
    '白底交付尺寸固定为1000×1000px',
):
    assert phrase in workflow, phrase

skill = (root / 'SKILL.md').read_text(encoding='utf-8')
prompts = (root / 'references' / 'prompts.md').read_text(encoding='utf-8')
for phrase in (
    '`internal_notes` 只记资料判断与素材缺口',
    '产品级 `illustration_system`',
    '`layout_regions`',
    '不得向旧提示词末尾追加',
    '`product`、`copy`、`composition`、`completeness`、`cross_page`',
    '`repair_attempts` 必须等于 `repairs` 条数',
    '`constraints` 只留在执行卡和审核记录',
    '`reference_exclusions`',
    '默认返修只改正向目标后重新 compose',
):
    assert phrase in workflow, phrase
for phrase in (
    '产品级 `illustration_system`',
    '默认返修修改执行卡的正向目标后重新 compose',
    '结构化审核',
):
    assert phrase in skill, phrase
assert '不在旧提示词末尾追加局部补丁' in prompts

first_party = [
    root / 'README.md',
    root / 'SKILL.md',
    root / 'references' / 'dependencies.md',
    root / 'references' / 'workflow.md',
    root / 'scripts' / 'README.md',
    root / 'scripts' / 'project_files.py',
    root / 'tools' / 'verify_package.py',
]
for path in first_party:
    content = path.read_text(encoding='utf-8')
    assert 'NumPy' not in content and 'numpy' not in content, path

print('PASS: release, product-content, prompt, review-state, dependency and white-material policies are complete.')
