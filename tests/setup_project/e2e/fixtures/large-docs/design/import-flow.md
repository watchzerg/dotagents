# 导入流程

![导入流程图](import-flow.png)

导入时先校验整份文件，再一次性追加，校验失败则不写入任何条目；校验规则对应函数 `validate_rows`。样例输入见 [sample-import.json](sample-import.json)。
