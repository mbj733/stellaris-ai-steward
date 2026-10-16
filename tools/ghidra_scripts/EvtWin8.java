// EvtWin8: 控制台命令注册/查找/执行链（含 resource / research_technology handler）
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class EvtWin8 extends GhidraScript {

    void decompileFn(long va, int cap) {
        Function f = getFunctionContaining(toAddr(va));
        if (f == null) {
            println("  (no function @0x" + Long.toHexString(va) + ")");
            return;
        }
        println("==== decompile " + f.getName() + " @0x" + Long.toHexString(f.getEntryPoint().getOffset()) + " (cap " + cap + ") ====");
        try {
            DecompInterface dec = new DecompInterface();
            dec.openProgram(currentProgram);
            DecompileResults res = dec.decompileFunction(f, 120, monitor);
            if (res != null && res.decompileCompleted()) {
                String[] lines = res.getDecompiledFunction().getC().split("\n");
                for (int i = 0; i < Math.min(lines.length, cap); i++) {
                    println("  " + lines[i]);
                }
                if (lines.length > cap) {
                    println("  ... (" + (lines.length - cap) + " more lines)");
                }
            } else {
                println("  (decompile failed)");
            }
            dec.dispose();
        } catch (Exception e) {
            println("  (decompile error " + e + ")");
        }
    }

    void allRefs(long va, String label) {
        println("==== ALL refs to " + label + " (0x" + Long.toHexString(va) + ") ====");
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(va))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  " + r.getReferenceType() + " from " + r.getFromAddress()
                    + " in " + (f != null ? f.getName() + "@0x" + Long.toHexString(f.getEntryPoint().getOffset()) : "?"));
            if (++n >= 20) {
                println("  ...");
                break;
            }
        }
    }

    @Override
    public void run() throws Exception {
        decompileFn(0x141b43650L, 130);   // 疑似执行（引用 "Unknown command"）
        decompileFn(0x141b435a0L, 90);    // 疑似查找/创建
        decompileFn(0x14016b4f0L, 60);    // 疑似取 console 全局
        decompileFn(0x140ee6e80L, 90);    // "resource" handler
        decompileFn(0x140ee6ef0L, 70);    // "research_technology" handler
        allRefs(0x141b43650L, "execute?");
        allRefs(0x141b435a0L, "lookup?");
        println("==== done ====");
    }
}
