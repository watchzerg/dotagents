# ADR 0001：金额使用 Decimal

状态：已采纳

背景：float 累加有误差，月末对账差 3 分钱。

决定：所有金额字段使用 `decimal.Decimal`，上下文精度 `prec=28`。

后果：序列化时需显式转字符串。
