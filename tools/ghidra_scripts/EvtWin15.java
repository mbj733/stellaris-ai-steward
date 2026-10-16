// EvtWin15: resource 命令逻辑 FUN_140ee51f0 + human_ai 应用路径 + 全局字符串
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;

public class EvtWin15 extends GhidraScript {

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
            DecompileResults res = dec.decompileFunction(f, 170, monitor);
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

    @Override
    public void run() throws Exception {
        decompileFn(0x140ee51f0L, 170);
        decompileFn(0x1405f88a0L, 80);

        println("==== global string @0x14289ee18 ====");
        long cap = getLong(toAddr(0x14289ee30L));
        long size = getLong(toAddr(0x14289ee28L));
        println("  size=" + size + " cap=" + cap);
        long dataPtr = 0x14289ee18L;
        if (0xf < cap) {
            dataPtr = getLong(toAddr(0x14289ee18L));
            println("  heap ptr=0x" + Long.toHexString(dataPtr));
        }
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < Math.min(size, 200); i++) {
            try {
                sb.append((char) (getByte(toAddr(dataPtr + i)) & 0xff));
            } catch (Exception e) {
                break;
            }
        }
        println("  content: '" + sb + "'");
        println("==== done ====");
    }
}
