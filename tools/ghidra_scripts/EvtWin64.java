// 找 game.log :88 成功日志行的写入函数：搜 "added info about event selection" / "selectedOption"
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import java.util.LinkedHashSet;

public class EvtWin64 extends GhidraScript {
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
                    println("  STR FOUND @" + hit + " block=" + b.getName());
                    return hit.getOffset();
                }
            } catch (Exception e) { }
        }
        return -1;
    }

    @Override
    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        LinkedHashSet<Long> funcs = new LinkedHashSet<>();
        for (String s : new String[]{"added info about event selection", "selectedOption %d", "selectedOption"}) {
            println("==== search: [" + s + "] ====");
            long a = findStr(s);
            if (a < 0) { println("  not found"); continue; }
            for (Reference r : getReferencesTo(toAddr(a))) {
                Function f = getFunctionContaining(r.getFromAddress());
                println("  ref " + r.getReferenceType() + " from 0x" + Long.toHexString(r.getFromAddress().getOffset())
                        + " in " + (f != null ? f.getName() + "@" + Long.toHexString(f.getEntryPoint().getOffset()) : "?"));
                if (f != null) funcs.add(f.getEntryPoint().getOffset());
            }
        }
        int n = 0;
        for (long f : funcs) {
            decomp(f, 60);
            if (++n >= 4) break;
        }
        println("==== callers of option-runner FUN_140a23740 ====");
        for (Reference r : getReferencesTo(toAddr(0x140a23740L))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  " + r.getReferenceType() + " from 0x" + Long.toHexString(r.getFromAddress().getOffset())
                    + " in " + (f != null ? f.getName() + "@" + Long.toHexString(f.getEntryPoint().getOffset()) : "?"));
        }
        println("==== done EvtWin64 ====");
    }
}
