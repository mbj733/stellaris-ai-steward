// EvtWin35: 分发器调用点剖析——param_1 是什么对象
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;

public class EvtWin35 extends GhidraScript {

    void decompileFn(long va, int cap) {
        Function f = getFunctionContaining(toAddr(va));
        if (f == null) {
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
            }
            dec.dispose();
        } catch (Exception e) {
        }
    }

    void asmAt(long va, int before, int after) {
        println("==== asm @0x" + Long.toHexString(va) + " ====");
        Instruction ins = getInstructionAt(toAddr(va));
        if (ins == null) {
            println("(no ins)");
            return;
        }
        for (int i = 0; i < before; i++) {
            Instruction p = ins.getPrevious();
            if (p == null) {
                break;
            }
            ins = p;
        }
        for (int i = 0; i < before + after; i++) {
            println("   " + ins.getAddress() + "  " + ins);
            ins = ins.getNext();
            if (ins == null) {
                break;
            }
        }
    }

    @Override
    public void run() throws Exception {
        asmAt(0x141378c5bL, 16, 4);   // FUN_141378c30 里对分发器的调用
        asmAt(0x14137ca64L, 16, 4);   // FUN_14137c560 里对分发器的调用
        decompileFn(0x141378c30L, 60);
        println("==== done ====");
    }
}
