import sys
import traceback

sys.path.insert(0, '.')

try:
    print("Trying to run main.py...", flush=True)
    
    # 导入 main 模块
    import main
    
    # 调用 main 函数
    main.main()
    
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}", flush=True)
    traceback.print_exc()
except SystemExit as e:
    print(f"SystemExit: {e}", flush=True)
except KeyboardInterrupt:
    print("KeyboardInterrupt", flush=True)
except BaseException as e:
    print(f"BaseException: {type(e).__name__}: {e}", flush=True)
    traceback.print_exc()