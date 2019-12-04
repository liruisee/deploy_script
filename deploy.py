import subprocess
import os
import sys
import time
from configparser import RawConfigParser
from log_tool.log_simple_util import get_logger

# 日志
logger = get_logger(app_name='deploy', is_debug=True, is_write_file=False)

# deploy_conf的路径，用于存储生产环境部署的配置文件
deploy_conf_dir = str(os.path.abspath(__file__)).rsplit('/', 1)[0] + '/server/deploy_conf'
# nginx转发uwsgi及asgi协议的配置模板
uwsgi_daphne_nginx_template_path = deploy_conf_dir + '/uwsgi_daphne_nginx_template.conf'
# nginx转发uwsgi及asgi协议的配置文件，由模板渲染变量之后得到
uwsgi_daphne_nginx_path = deploy_conf_dir + '/uwsgi_daphne_nginx.conf'
# uwsgi协议的配置模板
uwsgi_template_path = deploy_conf_dir + '/uwsgi_template.ini'
# uwsgi配置文件，由模板渲染变量之后得到
uwsgi_path = deploy_conf_dir + '/uwsgi.ini'
# python3文件路径
python3_path = "/usr/local/python3/bin"
# manage.py 文件路径
server_path = deploy_conf_dir.rsplit('/', 2)[0]
server_conf_path = f'{server_path}/server/conf'

# APP_ENV环境可选配置，在server_conf_path下
env_set = set([filename.replace('.ini', '') for filename in os.listdir(server_conf_path)])

# 本地nginx监听端口，建议填写80或者8000
if len(sys.argv) >= 2:
    nginx_listen_port = sys.argv[1]
else:
    nginx_listen_port = str(input("请输入nginx监听端口：")).strip()
    nginx_listen_port = '8000' if nginx_listen_port == '' else nginx_listen_port
# 目前前端ajax请求的是8000端口，所以如果不是8000端口，会有一些友好提示，如果自己输错了，可以选n，重新输入

while nginx_listen_port != '8000':
    is_sure = str(input(
        "非特殊需求，建议将端口设置为8000，当前端口为：%s，是否确定（y/n），y将继续执行，n将退出程序："
        % nginx_listen_port
    ))
    if is_sure.lower() == 'y':
        break
    nginx_listen_port = str(input("请输入nginx监听端口：")).strip()

# APP_ENV环境变量值
if len(sys.argv) >= 3:
    app_env = sys.argv[2]
else:
    app_env = str(input("请输入app_env环境变量，默认为dev：")).strip()
    app_env = 'dev' if app_env == '' else app_env

while app_env not in env_set:
    env_set_str = ', '.join(sorted(list(env_set)))
    app_env = str(input("app_env必须为【%s】其中之一，请请重新输入app_env环境变量：" % env_set_str)).strip()

# 初始化setting
config = RawConfigParser()
config_filepath = '%s/server/conf/%s.ini' % (str(os.path.abspath(__file__).rsplit('/', 1)[0]), app_env)
config.read(config_filepath)
logger.info(f'环境变量APP_ENV为：{app_env}')


# 渲染nginx和uwsgi配置文件模板
# 渲染模板的字典
args_dict = {
    'deploy_conf_dir': deploy_conf_dir,
    'server_path': server_path,
    'nginx_listen_port': nginx_listen_port
}

# 通过模板渲染nginx配置文件
with open(uwsgi_daphne_nginx_template_path, 'r', encoding='utf-8') as f_r:
    with open(uwsgi_daphne_nginx_path, 'wb') as f_w:
        content = f_r.read() % args_dict
        f_w.write(content.encode('utf-8'))

# 通过模板渲染uwsgi配置文件
with open(uwsgi_template_path, 'r', encoding='utf-8') as f_r:
    with open(uwsgi_path, 'wb') as f_w:
        content = f_r.read() % args_dict
        f_w.write(content.encode('utf-8'))

# 检测并更改最大连接数
max_conn_filepath = '/proc/sys/net/core/somaxconn'
f = open(max_conn_filepath, 'r')
max_conn_cnt = f.readline().rstrip('\n')
f.close()
if max_conn_cnt != '4096':
    cmd = f'echo 4096 > {max_conn_filepath}'
    subprocess.check_call(cmd, shell=True)

# 杀掉当前的uwsgi、nginx和manage.py进程，注意，是当前服务器所有的nginx和uwsgi进程，也就是说同一台服务器只能存在一个nginx和uwsgi进程
cmd = "ps aux|grep -E 'uwsgi|nginx|daphne|%s/manage' | grep -v 'grep' | awk '{print $2}' | xargs" % server_path
logger.info(cmd)
result = subprocess.getoutput(cmd)
logger.info(result)

if result == '':
    logger.info("进程已不存在，请勿重复执行")
else:
    cmd = 'kill -9 %s' % result
    subprocess.check_call(cmd, shell=True)
    logger.info("包含uwsgi或nginx 的进程kill成功")

# 配置环境变量
os.environ['APP_ENV'] = app_env
# 是否将日志打印到前天
os.environ['IS_DEBUG'] = '0'
# 同步数据库
cmd = "%s/python3 %s/manage.py migrate" % (python3_path, server_path)
logger.info(cmd)
subprocess.check_call(cmd, shell=True)
# 根据新的配置文件，启动nginx和uwsgi进程
cmd = "cd %s && /usr/local/python3/bin/uwsgi --ini %s && /usr/local/nginx/sbin/nginx -c %s" \
      % (server_path, uwsgi_path, uwsgi_daphne_nginx_path)
logger.info(cmd)
subprocess.check_call(cmd, shell=True)

# 待程序启动后查看进程是否存在，如果存在，则提供pid，如果不存在，则提示启动失败
time.sleep(1)
cmd = "ps aux|grep -E 'uwsgi|nginx' | grep -v 'grep' | awk '{print $2}' | xargs"
logger.info(cmd)
result = subprocess.check_output(cmd, shell=True)

if result == '':
    logger.info("进程启动失败，请检查相应的配置")
    logger.info("请到/usr/local/nginx/logs/error.log下查看nginx日志")
    logger.info("请到%s/uwsgi.log下查看uwsgi日志" % deploy_conf_dir)
else:
    logger.info("进程启动成功，进程id为：%s" % result)
    logger.info("查看进程请执行：ps aux|grep -E 'uwsgi|nginx'")

cmd = "sh %s/deploy.sh" % server_path
subprocess.check_call(cmd, shell=True)
time.sleep(1)
daphne_pid_file_path = f'{deploy_conf_dir}/daphne'
cmd = "ps aux | grep python3/bin/daphne | grep -v grep | awk '{print($2) > \"%s-\"NR\".pid\"}'" % daphne_pid_file_path
subprocess.call(cmd, shell=True)
