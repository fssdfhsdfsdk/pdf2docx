from ahk import AHK
import time

ahk = AHK()

"""
自动化GUI操作简单设计:
  点击添加
  点击取消任务
  点击具体任务
  点击输入框---> 输入目录名
  点击开始
  循环检测任务结束:
    判断任务是否成功,失败停止, 成功则继续
"""
def rmStartSpaceAndNewLines():
    cont = ahk.get_clipboard()
    lines = cont.splitlines()
    newLines = [x.strip() for x in lines]
    ahk.set_clipboard(" ".join(newLines))
    time.sleep(0.1)
    ahk.send_input("^v")
    time.sleep(0.1)

ahk.add_hotkey('^!b', callback=rmStartSpaceAndNewLines)
ahk.start_hotkeys()  # start the hotkey process thread
ahk.block_forever()  # not strictly needed in all scripts -- stops the script from exiting; sleep forever