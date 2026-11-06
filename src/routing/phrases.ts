export const FIXED_END_SESSION_PHRASES = [
  "退出",
  "退出对话",
  "停止对话",
  "退下",
  "你退下",
  "闭嘴",
  "住口",
  "退散",
  "够了",
  "下去",
  "请回",
  "省省",
  "少废话",
  "你烦不烦",
  "有完没完",
  "跪安",
  "可以了",
  "滚",
  "少啰嗦",
  "散会",
  "打住",
  "再见",
  "没事",
  "没事儿",
  "没事儿了",
  "没事了",
  "去睡觉",
  "晚安",
] as const;

export const FUZZY_END_SESSION_PHRASES = [
  "别说了",
  "到此为止",
  "无需多言",
  "识相的就走开",
  "这里没你的事了",
  "谈话可以结束了",
  "恕我失陪",
  "请勿打扰",
  "慢走不送",
  "拜托闭嘴好吗",
  "哪儿凉快哪儿待着去",
  "尔且退去",
  "阁下请自便",
  "到此结束",
  "不用再说了",
  "退出",
  "退下",
] as const;

export const END_SESSION_EXCLUDE_HINTS = [
  "什么",
  "什么意思",
  "怎么说",
  "翻译",
  "解释",
  "为什么",
  "含义",
  "意思",
] as const;

export const END_SESSION_TONE_SUFFIXES = ["吧", "呀", "啊", "呢", "啦", "嘛", "呗"] as const;
export const WAKE_WORD_CONTENTS = ["wake_word_detect", "测试人员测试。"] as const;
export const EXPLICIT_EXIT_CONTENT = "__EXIT__";

export const WAKE_REPLIES = [
  "你好，我在。",
  "我在呀。",
  "在呢。",
  "hello，我在。",
  "我在我在。",
  "我在，什么事。",
  "Hi~你好呀。",
  "Hi~你找我吗。",
  "找我什么事。",
  "你好呀。",
  "找我啥事。",
  "嘿！我在。",
  "我在。",
  "Hey，I am here. ",
  "嗨~我在。",
  "我在哦。",
] as const;

export const EXIT_REPLY = "那我先退下啦。";
export const CLEAR_REPLY = "已清除。";
export const UPLOAD_LOG_REPLY = "正在上传，";
export const IMAGE_FALLBACK_REPLY = "我还没解锁查看图片这个技能，你能跟我说说里面是什么吗？";
