// 通用 vtable 转储器：读取 _vt_target.txt 中的映像地址，列出槽位函数并反编译（供运行时 dump 后命名）
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import java.io.BufferedReader;
import java.io.FileReader;

public class EvtWin41 extends GhidraScript {
    @Override
    public void run() throws Exception {
        String path = "vt_target.txt";  // 输出去向，按需修改
        BufferedReader br = new BufferedReader(new FileReader(path));
        String line = br.readLine();
        br.close();
        long vt = Long.parseLong(line.trim(), 16);
        println("==== vtable @0x" + Long.toHexString(vt) + " 槽位表 ====");
        long[] fns = new long[24];
        for (int k = 0; k < 24; k++) {
            long q = getLong(toAddr(vt + k * 8L));
            fns[k] = q;
            Function f = getFunctionAt(toAddr(q));
            String tag = (q >= 0x140000000L && q < 0x146000000L) ? "" : "  (非代码区)";
            println("  [" + k + "] 0x" + Long.toHexString(q) + (f != null ? "  " + f.getName() : "") + tag);
        }
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        for (int k = 0; k < 24; k++) {
            long q = fns[k];
            if (q < 0x140000000L || q >= 0x146000000L) continue;
            Function f = getFunctionAt(toAddr(q));
            if (f == null) continue;
            DecompileResults res = di.decompileFunction(f, 60, monitor);
            println("---- 槽[" + k + "] " + f.getName() + " ----");
            String[] ls = res.getDecompiledFunction().getC().split("\n");
            for (int i = 0; i < Math.min(ls.length, 34); i++) println("    " + ls[i]);
        }
        println("==== done ====");
    }
}
