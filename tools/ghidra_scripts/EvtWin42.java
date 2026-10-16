// CSelectEventOptionCommand 溯源：找 lambda RTTI 描述符 → COL → vtable → 槽位函数与造类点
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

public class EvtWin42 extends GhidraScript {

    private long readQ(long a) {
        try { return getLong(toAddr(a)); } catch (Exception e) { return 0; }
    }

    @Override
    public void run() throws Exception {
        Memory mem = currentProgram.getMemory();
        // 候选 RTTI 类型描述符基址（字符串 0x1428bb3be / 0x1428bb42d 之前 0x10 处）
        long[] descs = { 0x1428bb3b0L, 0x1428bb3a0L, 0x1428bb420L, 0x1428bb410L };
        List<Long> hits = new ArrayList<>();
        for (long d : descs) {
            byte[] pat = new byte[8];
            long v = d;
            for (int i = 0; i < 8; i++) { pat[i] = (byte) (v & 0xff); v >>= 8; }
            Address a = mem.getMinAddress();
            while (a != null && hits.size() < 60) {
                Address f = mem.findBytes(a, pat, null, true, monitor);
                if (f == null) break;
                hits.add(f.getOffset());
                a = f.add(1);
            }
        }
        println("==== 指向 lambda 描述符的指针命中 = " + hits.size() + " 处 ====");
        Set<Long> cols = new LinkedHashSet<>();
        for (long h : hits) {
            println("  @0x" + Long.toHexString(h) + "  上下文: "
                    + " [h-0x10]=0x" + Long.toHexString(readQ(h - 0x10))
                    + " [h-8]=0x" + Long.toHexString(readQ(h - 8))
                    + " [h]=0x" + Long.toHexString(readQ(h))
                    + " [h+8]=0x" + Long.toHexString(readQ(h + 8)));
            // 可能是 COL 内的 pTypeDescriptor 字段；把附近 u32/u64 都当候选 COL 收集
            for (long off = -0x20; off <= 8; off += 4) {
                long cand = h + off;
                long q0 = readQ(cand);
                // COL 的 signature 常见为 1（x64）
                long sig = q0 & 0xffffffffL;
                if (sig == 1) cols.add(cand);
            }
        }
        println("==== 候选 COL = " + cols.size() + " 个 ====");
        Set<Long> vts = new LinkedHashSet<>();
        for (long c : cols) {
            println("  COL@0x" + Long.toHexString(c) + "  [0]=0x" + Long.toHexString(readQ(c))
                    + " [0x10]=0x" + Long.toHexString(readQ(c + 0x10)));
            for (Reference r : getReferencesTo(toAddr(c))) {
                println("    <- 被引用自 0x" + r.getFromAddress() + " (" + r.getReferenceType() + ")");
                vts.add(r.getFromAddress().getOffset() + 8);  // vtable 起点 = 引用点 + 8
            }
        }
        println("==== 候选 vtable = " + vts.size() + " 个 ====");
        for (long vt : vts) {
            println("  vtable@0x" + Long.toHexString(vt) + " 槽位:");
            for (int k = 0; k < 20; k++) {
                long q = readQ(vt + k * 8L);
                Function f = getFunctionAt(toAddr(q));
                println("    [" + k + "] 0x" + Long.toHexString(q)
                        + (f != null ? "  " + f.getName() : ""));
            }
            println("    造类点(代码引用该 vtable):");
            for (Reference r : getReferencesTo(toAddr(vt))) {
                Function f = getFunctionContaining(r.getFromAddress());
                println("      <- 0x" + r.getFromAddress() + " in "
                        + (f != null ? f.getName() + "@" + f.getEntryPoint() : "?"));
            }
        }
        println("==== done ====");
    }
}
