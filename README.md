# dailyfresh
完整的电商项目
＃项目流程

1、app:user  实现了用户注册、登陆、退出、用户个人信息面（user_info、user_order、user_site)等页面
>1、user使用的是继承的内部user类，登陆使用authenicate(user,name),判断user.is_authenicated来判定登陆状态

>2、注册需要邮箱激活验证，发送邮箱我们这里使用celery异步发送，这里的broker使用redis来存储

>3、user_info有一个最近浏览，我们把它存在redis中

2、app:goods  实现了首页，列表页，详情页
>1、首页的渲染，这里首页我们分为静态和动态的，因为我们的首页基本不会有太大的变化，用户一般都是访问首页，为了减少数据库的查询，所以我们先渲染一个静态页面，用户访问，我们直接返回这个页面，每当首页更改时，我们就重新生成静态页面，这里我们也使用celery异步生产，在项目中我使用celery_tasks.tasks发出异步任务，redis当broker，yibu_tasks.tasks当监听着，来执行任务（静态页面的使用最后在部署中会说到）

>2、列表页和详情页的生成，主要是对数据的查询还有就是模版的应用，稍微有点儿新东西就是动态属性的添加

>3、货物搜索，可以自己写一个简单的搜索，我们这里使用的是全文检索haystack,引擎whoosh，分词jieba中文分词，使用一是要添加search_index.py还有里面的内容，定义搜索的类，然后在固定位置建立索引字段

>4、图片存储在fdfs上nginx176.122.190.4:8888端口

3、app:cart   实现了购物车页面
>1、主要通过js和css实现添加购物车的画面显示，还有通过js来实现货物增减，最后就是把数据通过ajax发送给后台

>2、ajax.post发送数据我们需要添加csrf的参数

4、app:order  实现订单生成页面,订单支付，订单评论
>1、cart页面生成后，就是提交订单，提交订单user需要有默认地址，选择支付方式，我们这里使用的是支付宝支付

>2、选择相应的选项，然后提交进入user_order页面，显示当前的订单，然后尽心支付，支付我们使用的第三方支付接口（官方现在已有python sdk），直接跳转到网页支付界面，然后进行支付

>3、支付完成进行评论，最后是通过js实现detail页面描述和评论的切换

5、基本功能都已完成，最后就是部署
>1、我这里使用的nginx+uwsig

>2、nginx80:动态 走nginx+uwsig； 静态：静态文件（通过python manage.py collectstatic来收集）包含我们之前设定静态index页面我配置为8080

>3、EBUG = True  # 生产环境  False  ALLOWED_HOSTS = []  # ['*']

## 这里的配置文件只是一个实例，需要根据自己的需求进行配置
可参考settings_example
