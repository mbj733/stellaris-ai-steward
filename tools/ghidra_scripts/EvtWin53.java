// 全 .text 扫描：谁访问事件数据选项表 (+0x5e0 / +0x590)；并解剖附着函数
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.mem.MemoryBlock;
import java.util.LinkedHashMap;
import java.util.Map;

public class EvtWin53 extends GhidraScript {
    private DecompInterface di;

    private void decomp(long addr, int cap) {
        try {
            Function f = getFunctionAt(toAddr(addr));
            if (f == null) { println("(no fn 0x" + Long.toHexString(addr) + ")"); return; }
            DecompileResults res = di.decompileFunction(f, 60, monitor);
            println("==== " + f.getName() + " @0x" + Long.toHexString(addr) + " ====");
            String[] ls = res.getDecompiledFunction().getC().split("\n");
            for (int i = 0; i < Math.min(ls.length, cap); i++) println(ls[i]);
        } catch (Exception e) { println("fail 0x" + Long.toHexString(addr) + ": " + e); }
    }

    private void scanDisp(String needle, int cap) {
        println("==== scan instr '" + needle + "' ====");
        Map<String, Integer> byFn = new LinkedHashMap<>();
        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            if (!b.isExecute()) continue;
            long lo = b.getStart().getOffset(), hi = b.getEnd().getOffset();
            Instruction ins = currentProgram.getListing().getInstructionAt(b.getStart());
            if (ins == null) ins = currentProgram.getListing().getInstructionAfter(b.getStart());
            int guard = 0;
            while (ins != null && guard < 6000000) {
                long off = ins.getAddress().getOffset();
                if (off > hi) break;
                String s = ins.toString();
                if (s.contains(needle)) {
                    Function f = getFunctionContaining(ins.getAddress());
                    String key = (f != null ? f.getName() + "@0x" + Long.toHexString(f.getEntryPoint().getOffset()) : "?");
                    byFn.merge(key, 1, Integer::sum);
                }
                ins = ins.getNext();
                guard++;
            }
        }
        int n = 0;
        for (Map.Entry<String, Integer> e : byFn.entrySet()) {
            println("  " + e.getKey() + "  x" + e.getValue());
            if (++n >= cap) { println("  (cap)"); break; }
        }
    }

    @Override
    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        scanDisp("+ 0x5e0]", 80);
        scanDisp("+ 0x590]", 40);
        decomp(0x141bab870L, 60);
        decomp(0x1408e64d0L, 90);
        decomp(0x141013540L, 40);
        println("==== done ====");
    }
}
