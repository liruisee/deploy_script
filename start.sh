#!/bin/bash

env_set="var1,var2,var3,var4"

# 因为担心端口冲突，启动脚本需要传入端口号，可以用位置变量传，如果未传则会进入交互模式
if [[ $1 == "" ]]; then
    echo -n "请输入runserver所需端口号（如：8888）："
    read PORT
else
    PORT=${1}
fi

# 端口号检测
while true
do
    PORT=`/usr/local/python3/bin/python3 -c "print('${PORT}'.strip())"`
    if [[ ${PORT} == '8000' ]]; then
        # 获取监听端口信息
        echo -n "8000端口专为生产服务开放，请重新输入端口号："
        read PORT
    else
        break
    fi
done

# 获取APP_ENV的环境变量信息
if [[ $2 == "" ]]; then
    # 获取环境信息
    echo -n "请输入当前环境的APP_ENV环境变量（目前支持的环境有${env_set}）："
    read APP_ENV
else
    APP_ENV=`/usr/local/python3/bin/python3 -c "print('${2}'.strip())"`
fi

# env不正确会进入死循环
if [[ ${APP_ENV} == '' ]]; then
    APP_ENV="dev"
    echo "当前APP_ENV，为空字符串，将置为默认值dev"
else
    TRUE_ENV=`/usr/local/python3/bin/python3 -c "env_set=set('${env_set}'.split(','));print(int(('${APP_ENV}' in env_set)))"`
    while [[ ${TRUE_ENV} == "0" ]]
    do
        # 获取环境信息
        echo -n "请输入当前环境的APP_ENV环境变量："
        read APP_ENV
        TRUE_ENV=`/usr/local/python3/bin/python3 -c "env_set=set('${env_set}'.split(','));print(int(('${APP_ENV}' in env_set)))"`
    done
    APP_ENV=${APP_ENV}
fi

# start脚本所在目录文件夹
SCRIPT_PATH=$(cd `dirname $0`;pwd)
# python3解释器所在文件夹
PYTHON3_BIN=/usr/local/python3/bin
echo "SCRIPT_PATH:" ${SCRIPT_PATH}
echo "PYTHON3_BIN:" ${PYTHON3_BIN}

PIDS=`ps aux|grep "${SCRIPT_PATH}/manage.py" | grep -v 'grep' | awk '{print $2}' | xargs`
if [[ ${PIDS} != '' ]]; then
    kill -9 ${PIDS}
    echo "包含${SCRIPT_PATH}/manage.py 的进程kill成功"
else
    echo "进程已不存在，请勿重复执行"
fi

# 将APP_ENV，抛出，本脚本的子进程将全部生效，但在全局不会生效
export APP_ENV=${APP_ENV}
# 是否将日志打印到前台
export IS_DEBUG=0
# 启动服务
${PYTHON3_BIN}/python3 ${SCRIPT_PATH}/manage.py migrate
if [[ $? -ne 0 ]]; then
    exit
fi
nohup ${PYTHON3_BIN}/python3 ${SCRIPT_PATH}/manage.py runserver 0.0.0.0:${PORT} > ${SCRIPT_PATH}/log1 2>&1 &
nohup ${PYTHON3_BIN}/python3 ${SCRIPT_PATH}/manage.py server1 > ${SCRIPT_PATH}/log3 2>&1 &
