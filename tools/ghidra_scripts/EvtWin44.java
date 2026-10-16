// RTTI 溯源 v3：x64 MSVC RTTI 用 4 字节 RVA —— 扫 RVA 指向描述符/COL，链到 vtable 与造类点
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import java.util.ArrayList;
import java.util.List;

public class EvtWin44 extends GhidraScript {

    private long rdq(long a) {
        try { return getLong(toAddr(a)); } catch (Exception e) { return 0; }
    }

    @Override
    public void run() throws Exception {
        Memory mem = currentProgram.getMemory();
        // 1) 找 4 字节 RVA ∈ [0x28bb000,0x28bc000) 的位置（= COL 的 pTypeDescriptor 字段）
        List<Long> hits = new ArrayList<>();
        for (MemoryBlock b : mem.getBlocks()) {
            if (!b.isInitialized() || b.isExecute()) continue;
            long lo = b.getStart().getOffset(), hi = b.getEnd().getOffset();
            if (hi - lo > 0x2000000L) continue;
            byte[] data = new byte[(int) Math.min(hi - lo + 1, 0x2000000)];
            try { b.getBytes(b.getStart(), data, 0, data.length); } catch (Exception e) { continue; }
            for (int i = 0; i + 4 <= data.length; i += 4) {
                long v = (data[i] & 0xffL) | ((data[i+1] & 0xffL) << 8)
                       | ((data[i+2] & 0xffL) << 16) | ((data[i+3] & 0xffL) << 24);
                if (v >= 0x28bb000L && v < 0x28bc000L) {
                    println("  pType 候选 @0x" + Long.toHexString(lo + i) + " -> RVA 0x" + Long.toHexString(v));
                    hits.add(lo + i);
                    if (hits.size() > 40) break;
                }
            }
            if (hits.size() > 40) break;
        }
        println("==== pType 候选 = " + hits.size() + " ====");
        for (long h : hits) {
            long col = h - 0xC;               // COL: sig@0, off@4, cd@8, pType@0xC
            long colRva = col - 0x140000000L;
            println("  COL@0x" + Long.toHexString(col) + " (RVA 0x" + Long.toHexString(colRva) + ")"
                    + " 邻域: [col]=0x" + Long.toHexString(rdq(col))
                    + " [col+8]=0x" + Long.toHexString(rdq(col + 8)));
            // 2) 找引用该 COL 的 4 字节 RVA（= vtable 的 -8 槽）
            for (MemoryBlock b : mem.getBlocks()) {
                if (!b.isInitialized() || b.isExecute()) continue;
                long lo = b.getStart().getOffset(), hi = b.getEnd().getOffset();
                if (hi - lo > 0x2000000L) continue;
                byte[] data = new byte[(int) Math.min(hi - lo + 1, 0x2000000)];
                try { b.getBytes(b.getStart(), data, 0, data.length); } catch (Exception e) { continue; }
                for (int i = 0; i + 4 <= data.length; i += 4) {
                    long v = (data[i] & 0xffL) | ((data[i+1] & 0xffL) << 8)
                           | ((data[i+2] & 0xffL) << 16) | ((data[i+3] & 0xffL) << 24);
                    if (v == colRva) {
                        long vt = lo + i + 4;   // vtable 函数从这里开始
                        println("    vtable 候选 @0x" + Long.toHexString(vt) + " 槽位:");
                        for (int k = 0; k < 16; k++) {
                            long q = rdq(vt + k * 8L);
                            Function f = getFunctionAt(toAddr(q));
                            println("      [" + k + "] 0x" + Long.toHexString(q)
                                    + (f != null ? "  " + f.getName() : ""));
                        }
                        println("      造类点(代码引用):");
                        for (Reference r : getReferencesTo(toAddr(vt))) {
                            Function f = getFunctionContaining(r.getFromAddress());
                            println("        <- 0x" + r.getFromAddress()
                                    + (f != null ? " in " + f.getName() : ""));
                        }
                    }
                }
            }
            println("    ----");
        }
        println("==== done ====");
    }
}
