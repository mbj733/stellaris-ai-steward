// 找 :88 日志行写入函数 v2：字符串命中点 ±64 字节范围内的全部引用
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import java.util.LinkedHashSet;

public class EvtWin65 extends GhidraScript {
    private DecompInterface di;

    private void decomp(long addr, int cap) {
        try {
            Function f = getFunctionAt(toAddr(addr));
            if (f == null) f = getFunctionContaining(toAddr(addr));
            if (f == null) { println("(no fn 0x" + Long.toHexString(addr) + ")"); return; }
            DecompileResults res = di.decompileFunction(f, 90, monitor);
            println("==== " + f.getName() + " @0x" + Long.toHexString(f.getEntryPoint().getOffset()) + " ====");
            String[] ls = res.getDecompiledFunction().getC().split("\n");
            int n = Math.min(ls.length, cap);
            for (int i = 0; i < n; i++) println(ls[i]);
            if (ls.length > n) println("...(截断，全文 " + ls.length + " 行)");
        } catch (Exception e) { println("fail 0x" + Long.toHexString(addr) + ": " + e); }
    }

    private long findStr(String s) {
        Memory mem = currentProgram.getMemory();
        byte[] pat = s.getBytes();
        for (MemoryBlock b : mem.getBlocks()) {
            if (!b.isInitialized() || b.getSize() > 0x8000000L) continue;
            try {
                Address a = b.getStart();
                while (true) {
                    Address hit = mem.findBytes(a, b.getEnd(), pat, null, true, monitor);
                    if (hit == null) break;
                    return hit.getOffset();
                }
            } catch (Exception e) { }
        }
        return -1;
    }

    private void refsNear(long a, int back, int fwd, LinkedHashSet<Long> funcs) {
        for (long off = a - back; off <= a + fwd; off++) {
            for (Reference r : getReferencesTo(toAddr(off))) {
                Function f = getFunctionContaining(r.getFromAddress());
                println("  ref " + r.getReferenceType() + " to 0x" + Long.toHexString(off)
                        + " from 0x" + Long.toHexString(r.getFromAddress().getOffset())
                        + " in " + (f != null ? f.getName() + "@" + Long.toHexString(f.getEntryPoint().getOffset()) : "?"));
                if (f != null) funcs.add(f.getEntryPoint().getOffset());
            }
        }
    }

    @Override
    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        LinkedHashSet<Long> funcs = new LinkedHashSet<>();
        for (String s : new String[]{"added info about event selection", "playerEventId %d", "selectedOption"}) {
            println("==== search: [" + s + "] ====");
            long a = findStr(s);
            if (a < 0) { println("  not found"); continue; }
            println("  hit @0x" + Long.toHexString(a));
            byte[] around = new byte[96];
            try { currentProgram.getMemory().getBytes(toAddr(a - 48), around); } catch (Exception e) {}
            StringBuilder sb = new StringBuilder();
            for (byte c : around) sb.append(c >= 32 && c < 127 ? (char) c : '.');
            println("  ~bytes: " + sb);
            refsNear(a, 64, 16, funcs);
        }
        int n = 0;
        for (long f : funcs) {
            decomp(f, 55);
            if (++n >= 4) break;
        }
        println("==== done EvtWin65 ====");
    }
}
